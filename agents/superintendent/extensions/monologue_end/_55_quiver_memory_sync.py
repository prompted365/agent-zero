"""
Quiver Memory Sync — Parallel Persistence to RuVector GNN

Fires at monologue_end (after _50_memorize_fragments and _51_memorize_solutions).
Every time Mogul forms a new memory in FAISS, this extension dual-writes it to the
RuVector HNSW+GNN topology in the 'mogul_memory' collection.

FAISS = flat, subjective episodic recall (cosine similarity)
RuVector = deep, topological graph neural network (learns entity relationships)

Together they form the bicameral mind. Drift between them is measured by the
companion extension _55_quiver_drift_tracker.py at message_loop_prompts_after.
"""

import os
import json
import urllib.request
import urllib.error
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers import errors, settings
from python.helpers.dirty_json import DirtyJson
from python.helpers.defer import DeferredTask, THREAD_BACKGROUND
from agent import LoopData
from python.helpers.log import LogItem


RUVECTOR_URL = os.environ.get("RUVECTOR_URL", "http://host.docker.internal:6334")
COLLECTION = os.environ.get("RUVECTOR_MOGUL_COLLECTION", "mogul_memory")
DIMENSION = 384  # all-MiniLM-L6-v2 output dimension


class QuiverMemorySync(Extension):
    __version__ = "1.0.0"
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

            # Ensure collection exists in RuVector
            self._ensure_collection()

            # Dual-write each memory to RuVector
            synced = 0
            for memory in memories:
                txt = str(memory)
                try:
                    # Generate embedding using same model as FAISS
                    embedding = list(db.db.embedding_function.embed_query(txt))

                    payload = {
                        "text": txt,
                        "embedding": embedding,
                        "collection": COLLECTION,
                        "metadata": {
                            "area": "fragments",
                            "source": "quiver_sync",
                            "timestamp": Memory.get_timestamp(),
                        },
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
                        heading=f"RuVector sync partial: {synced} synced, error on next: {str(e)[:100]}"
                    )
                    break

            log_item.update(
                heading=f"Quiver sync: {synced}/{len(memories)} memories dual-written to RuVector GNN",
            )

        except Exception as e:
            err = errors.format_error(e)
            self.agent.context.log.log(
                type="warning",
                heading="Quiver memory sync error",
                content=err,
            )

    def _ensure_collection(self):
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
                    "dimension": DIMENSION,
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
        except urllib.error.URLError:
            pass  # RuVector not available — extensions should be resilient
