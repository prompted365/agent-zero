"""
Anchor Tension Tracker — Pattern-Anchored Memory Divergence Detection

Fires at message_loop_prompts_after (alongside _50_recall_memories).
Queries FAISS and RuVector for the current context, then computes:
  1. Semantic alignment via embedding centroid cosine similarity
  2. Pattern anchors via Harpoon priors module scanning
  3. Structural neighborhood from RuVector graph

Topic novelty (1 - semantic_alignment) replaces Jaccard distance.
Pattern anchors replace raw priors text dumps.
"""

import os
import sys
import json
import asyncio
import urllib.request
import urllib.error
import numpy as np
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers import errors, settings
from agent import LoopData
from python.helpers.log import LogItem

# Add extensions dir to path for _helpers import
_ext_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)
from _helpers.pattern_cache import scan_text as scan_pattern_anchors

RUVECTOR_URL = os.environ.get("RUVECTOR_URL", "http://host.docker.internal:6334")
COLLECTION = os.environ.get("RUVECTOR_MOGUL_COLLECTION", "mogul_memory")
DRIFT_THRESHOLD = float(os.environ.get("QUIVER_DRIFT_THRESHOLD", "0.60"))
DRIFT_CHECK_INTERVAL = int(os.environ.get("QUIVER_DRIFT_INTERVAL", "1"))
TOP_K = 5
CACHE_COSINE_THRESHOLD = 0.15


class AnchorTensionTracker(Extension):
    __version__ = "2.0.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "LoopData.extras_persistent[quiver_drift_data, quiver_drift, _drift_cache]"

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        set = settings.get_settings()
        if not set.get("memory_recall_enabled", True):
            return

        # Only check tension every N iterations
        if loop_data.iteration % DRIFT_CHECK_INTERVAL != 0:
            return

        log_item = self.agent.context.log.log(
            type="util",
            heading="Measuring anchor tension...",
        )

        try:
            await self._measure_tension(loop_data, log_item)
        except Exception as e:
            err = errors.format_error(e)
            log_item.update(
                heading="Anchor tension: RuVector not available (operating on FAISS only)",
            )

    async def _measure_tension(self, loop_data: LoopData, log_item: LogItem):
        # Build search query from current context
        user_msg = loop_data.user_message.output_text() if loop_data.user_message else ""
        history = self.agent.history.output_text()[-2000:]
        query = f"{user_msg}\n{history}".strip()

        if not query or len(query) < 10:
            log_item.update(heading="Anchor tension: insufficient context.")
            return

        # Get FAISS memory
        db = await Memory.get(self.agent)

        # Generate embedding for the query
        query_embedding = np.array(db.db.embedding_function.embed_query(query[:1000]))

        # Check monologue-level cache: if query embedding hasn't shifted
        # significantly, reuse prior FAISS/RuVector results (stores don't
        # change mid-monologue -- sync fires at monologue_end)
        cache = loop_data.extras_persistent.get("_drift_cache")
        if cache is not None and not cache.get("ruvector_failed"):
            cached_emb = np.array(cache["query_embedding"])
            cos_dist = 1.0 - float(
                np.dot(query_embedding, cached_emb)
                / (np.linalg.norm(query_embedding) * np.linalg.norm(cached_emb) + 1e-9)
            )
            if cos_dist < CACHE_COSINE_THRESHOLD:
                log_item.update(heading=f"Tension cache hit (cos_dist={cos_dist:.4f})")
                # Re-expose structured data from cache for ecotone gate
                if drift_data := cache.get("drift_data"):
                    loop_data.extras_persistent["quiver_drift_data"] = drift_data
                return

        embedding = query_embedding.tolist()

        # Search FAISS
        faiss_docs = await db.search_similarity_threshold(
            query=query[:1000],
            limit=TOP_K,
            threshold=0.5,
            filter=f"area == '{Memory.Area.MAIN.value}' or area == '{Memory.Area.FRAGMENTS.value}'",
        )
        faiss_texts = [doc.page_content[:200] for doc in faiss_docs]

        # Compute FAISS centroid embedding
        faiss_embeddings = []
        for doc in faiss_docs:
            emb = np.array(db.db.embedding_function.embed_query(doc.page_content[:500]))
            faiss_embeddings.append(emb)
        faiss_centroid = np.mean(faiss_embeddings, axis=0) if faiss_embeddings else query_embedding

        # Search RuVector
        ruvector_texts = []
        ruvector_ids = []
        ruvector_failed = False
        try:
            payload = {
                "embedding": embedding,
                "top_k": TOP_K,
                "collection": COLLECTION,
            }
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{RUVECTOR_URL}/search",
                data=body,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())

            for r in result.get("results", []):
                ruvector_texts.append(r.get("text", "")[:200])
                if r.get("id"):
                    ruvector_ids.append(str(r["id"]))

        except (urllib.error.URLError, Exception):
            ruvector_failed = True
            log_item.update(heading="Anchor tension: RuVector unreachable, FAISS-only mode.")

        if not faiss_texts and not ruvector_texts:
            log_item.update(heading="Anchor tension: no memories in either system.")
            return

        # Compute RuVector centroid embedding
        ruvector_embeddings = []
        for txt in ruvector_texts:
            emb = np.array(db.db.embedding_function.embed_query(txt[:500]))
            ruvector_embeddings.append(emb)
        ruvector_centroid = np.mean(ruvector_embeddings, axis=0) if ruvector_embeddings else query_embedding

        # Semantic alignment via cosine similarity of centroids
        if faiss_embeddings and ruvector_embeddings:
            dot = float(np.dot(faiss_centroid, ruvector_centroid))
            norm = float(np.linalg.norm(faiss_centroid) * np.linalg.norm(ruvector_centroid) + 1e-9)
            semantic_alignment = max(0.0, min(1.0, dot / norm))
        else:
            semantic_alignment = 1.0  # Only one system available, no divergence measurable

        topic_novelty = 1.0 - semantic_alignment

        # Pattern anchors from priors modules via Harpoon pattern scan
        context_text = f"{user_msg}\n{history}"
        pattern_anchors = scan_pattern_anchors(context_text)

        # RuVector graph neighborhood (structural context)
        ruvector_neighbors = []
        for rid in ruvector_ids[:3]:
            try:
                req = urllib.request.Request(f"{RUVECTOR_URL}/graph/neighbors/{rid}")
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    nbr_result = json.loads(resp.read().decode())
                for n in nbr_result.get("neighbors", [])[:3]:
                    text = n.get("text", n.get("label", ""))[:150]
                    if text:
                        ruvector_neighbors.append(text)
            except Exception:
                pass  # Graph endpoint may not exist yet

        # Build drift data (backward compatible key "drift" = topic_novelty)
        drift_data = {
            "drift": topic_novelty,
            "semantic_alignment": semantic_alignment,
            "topic_novelty": topic_novelty,
            "pattern_anchors": pattern_anchors,
            "ruvector_neighbors": ruvector_neighbors,
            "faiss_texts": faiss_texts,
            "ruvector_texts": ruvector_texts,
        }

        if topic_novelty >= DRIFT_THRESHOLD:
            loop_data.extras_persistent["quiver_drift_data"] = drift_data
        else:
            loop_data.extras_persistent.pop("quiver_drift_data", None)

        # Cache results + embedding for subsequent iterations in this monologue
        # If RuVector failed, mark cache so next iteration retries instead of serving stale data
        loop_data.extras_persistent["_drift_cache"] = {
            "query_embedding": embedding,
            "drift_data": drift_data,
            "ruvector_failed": ruvector_failed,
        }

        log_item.update(
            heading=(
                f"Anchor tension: {topic_novelty:.2f} "
                f"(alignment={semantic_alignment:.2f}, "
                f"FAISS={len(faiss_texts)}, RuVector={len(ruvector_texts)}, "
                f"anchors={len(pattern_anchors)})"
            ),
        )

        # Build injection blocks
        injection_parts = []

        if topic_novelty >= DRIFT_THRESHOLD and ruvector_texts:
            # STRUCTURAL CONTEXT (was COLLECTIVE CENTER)
            structural_items = ruvector_neighbors[:5] if ruvector_neighbors else ruvector_texts[:3]
            structural_text = "\n".join(f"  - {item}" for item in structural_items)

            injection_parts.append(
                f"\n\n[ANCHOR TENSION: {topic_novelty:.2f}]\n"
                f"Your FAISS episodic recall and RuVector GNN topology show "
                f"semantic alignment of {semantic_alignment:.2f} for this context.\n\n"
                f"[STRUCTURAL CONTEXT \u2014 RuVector GNN]\n"
                f"{structural_text}\n"
                f"[/STRUCTURAL CONTEXT]\n\n"
                f"Analyze this divergence: is each item undiscovered, stale, "
                f"parallel-valid, noise, or an actionable gap?"
            )

        # PATTERN RESONANCE (was PRIOR ANCHOR) -- inject when anchors found
        if pattern_anchors:
            anchor_lines = []
            for a in pattern_anchors[:8]:
                anchor_lines.append(f'  - "{a["term"]}" ({a["module_id"]}, {a["domain"]})')
            resonance_text = "\n".join(anchor_lines)

            injection_parts.append(
                f"\n\n[PATTERN RESONANCE]\n"
                f"Current context maps to {len(pattern_anchors)} civilization patterns:\n"
                f"{resonance_text}\n"
                f"[/PATTERN RESONANCE]\n\n"
                f"These are long-lived narrative invariants. If your response "
                f"diverges from them, note the departure \u2014 it may be valid."
            )

        if injection_parts:
            loop_data.extras_persistent["quiver_drift"] = "".join(injection_parts)
            log_item.update(
                heading=(
                    f"HIGH TENSION {topic_novelty:.2f}: Injected Structural Context"
                    f"{' + Pattern Resonance' if pattern_anchors else ''}"
                ),
            )
        else:
            loop_data.extras_persistent.pop("quiver_drift", None)
            log_item.update(
                heading=f"Anchors aligned: tension={topic_novelty:.2f} (threshold={DRIFT_THRESHOLD})",
            )
