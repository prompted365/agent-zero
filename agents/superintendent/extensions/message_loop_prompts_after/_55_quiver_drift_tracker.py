"""
Quiver Drift Tracker — Tri-Cameral Memory Drift Detection

Fires at message_loop_prompts_after (alongside _50_recall_memories).
Queries FAISS, RuVector, and the civilization_priors collection for
the current context, then computes pairwise Jaccard distances.

Three drift axes:
  - drift (primary): FAISS vs RuVector (episodic vs topological)
  - drift_episodic_priors: FAISS vs civilization priors
  - drift_topological_priors: RuVector vs civilization priors

If primary drift exceeds threshold (0.60), RuVector's unique findings
are injected as [COLLECTIVE CENTER]. If priors drift is high, unique
priors context is injected as [PRIOR ANCHOR].

This implements drift measurement in the many-dimensioned quiver space.
"""

import os
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


RUVECTOR_URL = os.environ.get("RUVECTOR_URL", "http://host.docker.internal:6334")
COLLECTION = os.environ.get("RUVECTOR_MOGUL_COLLECTION", "mogul_memory")
PRIORS_COLLECTION = os.environ.get("RUVECTOR_PRIORS_COLLECTION", "civilization_priors")
DRIFT_THRESHOLD = float(os.environ.get("QUIVER_DRIFT_THRESHOLD", "0.60"))
DRIFT_CHECK_INTERVAL = int(os.environ.get("QUIVER_DRIFT_INTERVAL", "1"))  # every N iterations
TOP_K = 5
MAX_COLLECTIVE_CENTER_CHARS = 800
MAX_PRIOR_ANCHOR_CHARS = 600
CACHE_COSINE_THRESHOLD = 0.15  # reuse cached results if embedding shift < this


class QuiverDriftTracker(Extension):
    __version__ = "1.1.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "LoopData.extras_persistent[quiver_drift_data, quiver_drift, _drift_cache]"

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        set = settings.get_settings()
        if not set.get("memory_recall_enabled", True):
            return

        # Only check drift every N iterations
        if loop_data.iteration % DRIFT_CHECK_INTERVAL != 0:
            return

        log_item = self.agent.context.log.log(
            type="util",
            heading="Measuring quiver space drift...",
        )

        try:
            await self._measure_drift(loop_data, log_item)
        except Exception as e:
            err = errors.format_error(e)
            log_item.update(
                heading="Drift tracker: RuVector not available (operating on FAISS only)",
            )

    async def _measure_drift(self, loop_data: LoopData, log_item: LogItem):
        # Build search query from current context
        user_msg = loop_data.user_message.output_text() if loop_data.user_message else ""
        history = self.agent.history.output_text()[-2000:]
        query = f"{user_msg}\n{history}".strip()

        if not query or len(query) < 10:
            log_item.update(heading="Drift tracker: insufficient context for measurement.")
            return

        # Get FAISS memory
        db = await Memory.get(self.agent)

        # Generate embedding for the query
        query_embedding = np.array(db.db.embedding_function.embed_query(query[:1000]))

        # Check monologue-level cache: if query embedding hasn't shifted
        # significantly, reuse prior FAISS/RuVector results (stores don't
        # change mid-monologue — sync fires at monologue_end)
        cache = loop_data.extras_persistent.get("_drift_cache")
        if cache is not None:
            # If RuVector failed previously, skip cache to allow retry
            if cache.get("ruvector_failed"):
                log_item.update(heading="Drift cache: RuVector was down, retrying...")
            else:
                cached_emb = np.array(cache["query_embedding"])
                cos_dist = 1.0 - float(
                    np.dot(query_embedding, cached_emb)
                    / (np.linalg.norm(query_embedding) * np.linalg.norm(cached_emb) + 1e-9)
                )
                if cos_dist < CACHE_COSINE_THRESHOLD:
                    log_item.update(heading=f"Drift cache hit (cos_dist={cos_dist:.4f})")
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
        faiss_texts = set(doc.page_content[:200] for doc in faiss_docs)

        # Search RuVector
        ruvector_texts = set()
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
                text = r.get("text", "")[:200]
                ruvector_texts.add(text)

        except (urllib.error.URLError, Exception):
            ruvector_failed = True
            log_item.update(heading="Drift tracker: RuVector unreachable, FAISS-only mode.")
        else:
            ruvector_failed = False

        if not faiss_texts and not ruvector_texts:
            log_item.update(heading="Drift tracker: no memories in either system yet.")
            return

        # Search civilization_priors collection (third chamber, degrades gracefully)
        priors_texts = set()
        try:
            payload = {
                "embedding": embedding,
                "top_k": TOP_K,
                "collection": PRIORS_COLLECTION,
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
                text = r.get("text", "")[:200]
                priors_texts.add(text)
        except Exception:
            pass  # Priors not available — degrade to bicameral

        # Compute Jaccard distance between the two primary result sets
        # Jaccard = |intersection| / |union|
        # Drift = 1 - Jaccard (0 = identical, 1 = completely different)
        intersection = faiss_texts & ruvector_texts
        union = faiss_texts | ruvector_texts

        if not union:
            drift = 0.0
        else:
            jaccard = len(intersection) / len(union)
            drift = 1.0 - jaccard

        # Pairwise drift for tri-cameral measurement
        drift_episodic_priors = self._jaccard_distance(faiss_texts, priors_texts)
        drift_topological_priors = self._jaccard_distance(ruvector_texts, priors_texts)

        # Find unique texts from each system
        ruvector_unique_texts = ruvector_texts - faiss_texts
        faiss_unique_texts = faiss_texts - ruvector_texts
        priors_unique_texts = priors_texts - faiss_texts - ruvector_texts

        # Expose structured drift data for downstream gates (ecotone integrity)
        drift_data = {
            "drift": drift,
            "drift_episodic_priors": drift_episodic_priors,
            "drift_topological_priors": drift_topological_priors,
            "faiss_texts": list(faiss_texts),
            "ruvector_texts": list(ruvector_texts),
            "priors_texts": list(priors_texts),
            "ruvector_unique_texts": list(ruvector_unique_texts),
            "faiss_unique_texts": list(faiss_unique_texts),
            "priors_unique_texts": list(priors_unique_texts),
            "overlap_texts": list(intersection),
        }

        if drift >= DRIFT_THRESHOLD:
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

        priors_label = f", priors={len(priors_texts)}" if priors_texts else ""
        log_item.update(
            heading=f"Quiver drift: {drift:.2f} (FAISS={len(faiss_texts)}, RuVector={len(ruvector_texts)}, overlap={len(intersection)}{priors_label})",
        )

        # Build injection blocks
        injection_parts = []

        # If primary drift exceeds threshold, inject collective center (capped to prevent OOM)
        if drift >= DRIFT_THRESHOLD and ruvector_unique_texts:
            parts = []
            total = 0
            for txt in ruvector_unique_texts:
                if total + len(txt) > MAX_COLLECTIVE_CENTER_CHARS:
                    break
                parts.append(txt)
                total += len(txt)
            collective_center = "\n\n".join(parts) if parts else list(ruvector_unique_texts)[0][:MAX_COLLECTIVE_CENTER_CHARS]

            injection_parts.append(
                f"\n\n[QUIVER DRIFT ALERT: {drift:.2f}]\n"
                f"Your FAISS local memory and RuVector GNN topology are diverging.\n"
                f"RuVector's self-learning graph has found {len(ruvector_unique_texts)} "
                f"structurally relevant memories that your flat FAISS search missed.\n\n"
                f"[COLLECTIVE CENTER — RuVector GNN unique context]\n"
                f"{collective_center}\n"
                f"[/COLLECTIVE CENTER]\n\n"
                f"Re-center your reasoning against this topological context before responding."
            )

        # If priors drift is high AND there are unique priors, inject prior anchor
        if priors_unique_texts and (drift_episodic_priors >= DRIFT_THRESHOLD or drift_topological_priors >= DRIFT_THRESHOLD):
            parts = []
            total = 0
            for txt in priors_unique_texts:
                if total + len(txt) > MAX_PRIOR_ANCHOR_CHARS:
                    break
                parts.append(txt)
                total += len(txt)
            prior_anchor = "\n\n".join(parts) if parts else list(priors_unique_texts)[0][:MAX_PRIOR_ANCHOR_CHARS]

            injection_parts.append(
                f"\n\n[PRIOR ANCHOR — Civilization Priors unique context]\n"
                f"{prior_anchor}\n"
                f"[/PRIOR ANCHOR]\n\n"
                f"Ground your response against these long-lived narrative invariants."
            )

        if injection_parts:
            loop_data.extras_persistent["quiver_drift"] = "".join(injection_parts)

            log_item.update(
                heading=(
                    f"HIGH DRIFT {drift:.2f}: Injected Collective Center"
                    f"{' + Prior Anchor' if len(injection_parts) > 1 else ''}"
                ),
                drift_score=f"{drift:.4f}",
                drift_ep=f"{drift_episodic_priors:.4f}" if priors_texts else "n/a",
                drift_tp=f"{drift_topological_priors:.4f}" if priors_texts else "n/a",
                faiss_count=str(len(faiss_texts)),
                ruvector_count=str(len(ruvector_texts)),
                priors_count=str(len(priors_texts)),
                overlap=str(len(intersection)),
                unique_ruvector=str(len(ruvector_unique_texts)),
                unique_priors=str(len(priors_unique_texts)),
            )
        else:
            # Low drift — systems are aligned
            if "quiver_drift" in loop_data.extras_persistent:
                del loop_data.extras_persistent["quiver_drift"]

            log_item.update(
                heading=f"Quiver aligned: drift={drift:.2f} (threshold={DRIFT_THRESHOLD})",
                drift_score=f"{drift:.4f}",
            )

    @staticmethod
    def _jaccard_distance(set_a: set, set_b: set) -> float:
        """Compute Jaccard distance between two sets. Returns 0.0 if both empty."""
        if not set_a and not set_b:
            return 0.0
        union = set_a | set_b
        if not union:
            return 0.0
        return 1.0 - len(set_a & set_b) / len(union)
