"""
Quiver Memory Sync — Enriched Persistence to RuVector GNN

Fires at monologue_end (after _50_memorize_fragments and _51_memorize_solutions).
Dual-writes memories from FAISS to RuVector, then enriches with:
  1. Entity extraction via utility model
  2. Pattern tagging via Harpoon priors modules
  3. Graph edge creation in RuVector
  4. SONA trajectory feed for self-learning metrics
"""

import os
import sys
import json
import logging
import urllib.request
import urllib.error
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers import errors, settings
from python.helpers.dirty_json import DirtyJson
from python.helpers.defer import DeferredTask, THREAD_BACKGROUND
from agent import LoopData
from python.helpers.log import LogItem

# Add extensions dir to path for _helpers import
_ext_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)
from _helpers.pattern_cache import scan_text as scan_pattern_anchors

RUVECTOR_URL = os.environ.get("RUVECTOR_URL", "http://host.docker.internal:6334")
COLLECTION = os.environ.get("RUVECTOR_MOGUL_COLLECTION", "mogul_memory")

logger = logging.getLogger(__name__)


class QuiverMemorySync(Extension):
    __version__ = "2.0.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "LoopData (read-only, no extras_persistent writes)"

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        set = settings.get_settings()
        if not set.get("memory_memorize_enabled", True):
            return

        log_item = self.agent.context.log.log(
            type="util",
            heading="Syncing to RuVector collective memory...",
        )

        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(self._sync, loop_data, log_item)
        return task

    async def _sync(self, loop_data: LoopData, log_item: LogItem, **kwargs):
        try:
            # Get FAISS memory to access embedder
            db = await Memory.get(self.agent)

            # Extract memories from current conversation (same approach as memorize_fragments)
            # Cap history text to prevent OOM during utility model call when
            # conversation + Collective Center injection accumulates
            system = self.agent.read_prompt("memory.memories_sum.sys.md")
            msgs_text = self.agent.concat_messages(self.agent.history)
            if len(msgs_text) > 4000:
                msgs_text = msgs_text[-4000:]

            memories_json = await self.agent.call_utility_model(
                system=system,
                message=msgs_text,
                background=True,
            )

            if not memories_json or not isinstance(memories_json, str):
                log_item.update(heading="No memories to sync to RuVector.")
                return

            memories_json = memories_json.strip()
            if not memories_json:
                return

            try:
                memories = DirtyJson.parse_string(memories_json)
            except Exception:
                log_item.update(heading="Failed to parse memories for RuVector sync.")
                return

            if not isinstance(memories, list):
                memories = [memories] if memories else []
            if not memories:
                log_item.update(heading="No memories to sync.")
                return

            # Compute embedding dimension from the active model (supports model migration)
            dimension = len(db.db.embedding_function.embed_query("dimension probe"))

            # Ensure collection exists in RuVector with correct dimension
            self._ensure_collection(dimension)

            # Pre-compute texts and scan for pattern anchors so tags
            # can be baked into each document's metadata at creation time
            combined_texts = [str(m) for m in memories]
            combined_text = "\n".join(combined_texts)[:2000]

            pattern_matches = []
            try:
                pattern_matches = scan_pattern_anchors(combined_text)
            except Exception:
                pass

            pattern_tags = [m["term"] for m in pattern_matches]
            pattern_domains = list(set(m["domain"] for m in pattern_matches))

            # Step 0: Dual-write each memory to RuVector with pattern metadata
            synced = 0
            for i, memory in enumerate(memories):
                txt = combined_texts[i]
                try:
                    # Generate embedding using same model as FAISS
                    embedding = list(db.db.embedding_function.embed_query(txt))

                    metadata = {
                        "area": "fragments",
                        "source": "quiver_sync",
                        "timestamp": Memory.get_timestamp(),
                    }
                    if pattern_tags:
                        metadata["pattern_tags"] = pattern_tags
                        metadata["pattern_domains"] = pattern_domains

                    payload = {
                        "text": txt,
                        "embedding": embedding,
                        "collection": COLLECTION,
                        "metadata": metadata,
                    }

                    body = json.dumps(payload).encode()
                    req = urllib.request.Request(
                        f"{RUVECTOR_URL}/documents",
                        data=body,
                        method="POST",
                    )
                    req.add_header("Content-Type", "application/json")
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        resp.read()
                    synced += 1

                except (urllib.error.URLError, Exception) as e:
                    # RuVector might not be running — log but don't crash
                    log_item.update(
                        heading=f"RuVector sync partial: {synced} synced, error: {str(e)[:100]}"
                    )
                    continue

            # Step 1: Build/rebuild graph from document embeddings
            graph_built = False
            if synced > 0:
                try:
                    payload = {"collection": COLLECTION, "similarity_threshold": 0.7}
                    body = json.dumps(payload).encode()
                    req = urllib.request.Request(
                        f"{RUVECTOR_URL}/graph/build",
                        data=body,
                        method="POST",
                    )
                    req.add_header("Content-Type", "application/json")
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        resp.read()
                    graph_built = True
                except Exception as e:
                    logger.warning(f"Graph build failed: {str(e)[:200]}")

            # Step 2: Entity extraction via utility model
            entities = []
            try:
                entities = await self._extract_entities(combined_text)
            except Exception as e:
                logger.warning(f"Entity extraction failed: {str(e)[:200]}")

            # Step 3: Graph edge creation from entities
            edges_created = 0
            try:
                edges_created = self._create_graph_edges(entities, db)
            except Exception as e:
                logger.warning(f"Graph edge creation failed: {str(e)[:200]}")

            # Step 4: SONA trajectory feed
            try:
                self._feed_sona_trajectory(synced, len(entities), len(pattern_matches))
            except Exception:
                pass

            log_item.update(
                heading=(
                    f"Quiver sync: {synced}/{len(memories)} memories, "
                    f"{len(entities)} entities, {len(pattern_matches)} pattern anchors, "
                    f"{edges_created} graph edges"
                    f"{', graph rebuilt' if graph_built else ''}"
                ),
            )

        except Exception as e:
            err = errors.format_error(e)
            self.agent.context.log.log(
                type="warning",
                heading="Quiver memory sync error",
                content=err,
            )

    async def _extract_entities(self, text: str) -> list[dict]:
        """Extract entities from memory text via utility model."""
        prompt_msg = self.agent.read_prompt("memory_entity_extraction.md", memories_text=text)
        result = await self.agent.call_utility_model(
            system="You are an entity extraction engine. Return ONLY valid JSON.",
            message=prompt_msg,
            background=True,
        )
        if not result:
            return []
        result = result.strip()
        # Handle markdown code fences
        if result.startswith("```"):
            import re
            result = re.sub(r"^```(?:json)?\s*", "", result)
            result = re.sub(r"\s*```$", "", result)
        try:
            parsed = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Entity extraction returned invalid JSON: {str(result)[:200]}")
            parsed = {"entities": []}
        if isinstance(parsed, dict):
            return parsed.get("entities", [parsed])
        return parsed if isinstance(parsed, list) else []

    def _create_graph_edges(self, entities: list[dict], db) -> int:
        """Create entity nodes and relationship edges in RuVector graph."""
        edges = 0
        for entity in entities:
            name = entity.get("name", "")
            etype = entity.get("type", "UNKNOWN")
            if not name:
                continue
            # Upsert entity node
            node_id = f"entity:{name.lower().replace(' ', '_')}"
            try:
                embedding = list(db.db.embedding_function.embed_query(name))
                payload = {
                    "id": node_id,
                    "text": name,
                    "embedding": embedding,
                    "collection": COLLECTION,
                    "metadata": {
                        "type": etype,
                        "source": "entity_extraction",
                        "is_entity": True,
                    },
                }
                body = json.dumps(payload).encode()
                req = urllib.request.Request(
                    f"{RUVECTOR_URL}/documents",
                    data=body,
                    method="POST",
                )
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    resp.read()
            except Exception:
                continue
            # Create edges for relationships via /graph/edges endpoint
            for rel in entity.get("relationships", []):
                target = rel.get("target", "")
                rel_type = rel.get("type", "RELATED_TO")
                if not target:
                    continue
                target_id = f"entity:{target.lower().replace(' ', '_')}"
                try:
                    payload = {
                        "source": node_id,
                        "target": target_id,
                        "edge_type": rel_type,
                    }
                    body = json.dumps(payload).encode()
                    req = urllib.request.Request(
                        f"{RUVECTOR_URL}/graph/edges",
                        data=body,
                        method="POST",
                    )
                    req.add_header("Content-Type", "application/json")
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        resp.read()
                    edges += 1
                except Exception:
                    pass
        return edges

    def _feed_sona_trajectory(self, memory_count: int, entity_count: int, pattern_count: int):
        """Feed sync metrics to SONA trajectory endpoint."""
        payload = {
            "memory_count": memory_count,
            "entity_count": entity_count,
            "pattern_anchors": pattern_count,
            "timestamp": Memory.get_timestamp(),
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{RUVECTOR_URL}/sona/trajectory",
            data=body,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()

    def _ensure_collection(self, dimension: int):
        """Create the mogul_memory collection if it doesn't exist."""
        try:
            req = urllib.request.Request(f"{RUVECTOR_URL}/collections/{COLLECTION}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Collection doesn't exist, create it
                payload = {
                    "name": COLLECTION,
                    "dimension": dimension,
                    "metric": "cosine",
                }
                body = json.dumps(payload).encode()
                req = urllib.request.Request(
                    f"{RUVECTOR_URL}/collections",
                    data=body,
                    method="POST",
                )
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp.read()
            else:
                logger.warning(f"RuVector collection check failed ({e.code}): {str(e)[:200]}")
        except urllib.error.URLError:
            pass  # RuVector not available — extensions should be resilient
