"""
Quiver Drift Tracker — Bicameral Memory Drift Detection

Fires at message_loop_prompts_after (alongside _50_recall_memories).
Queries BOTH FAISS and RuVector simultaneously for the current context,
then computes Jaccard distance between the two result sets.

If drift exceeds threshold (0.60), it means RuVector's self-learning GNN
has found structurally different, deeper context than flat FAISS similarity.
When this happens, Mogul receives a system-level alert with RuVector's unique
findings injected as the [COLLECTIVE CENTER] — forcing mathematical re-centering
before the next response.

This implements drift measurement in the many-dimensioned quiver space.
"""

import os
import json
import asyncio
import urllib.request
import urllib.error
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers import errors, settings
from agent import LoopData
from python.helpers.log import LogItem


RUVECTOR_URL = os.environ.get("RUVECTOR_URL", "http://host.docker.internal:6334")
COLLECTION = os.environ.get("RUVECTOR_MOGUL_COLLECTION", "mogul_memory")
DRIFT_THRESHOLD = float(os.environ.get("QUIVER_DRIFT_THRESHOLD", "0.60"))
DRIFT_CHECK_INTERVAL = int(os.environ.get("QUIVER_DRIFT_INTERVAL", "1"))  # every N iterations
TOP_K = 8


class QuiverDriftTracker(Extension):

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
        embedding = list(db.db.embedding_function.embed_query(query[:1000]))

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
        ruvector_unique = []
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
            log_item.update(heading="Drift tracker: RuVector unreachable, FAISS-only mode.")
            return

        if not faiss_texts and not ruvector_texts:
            log_item.update(heading="Drift tracker: no memories in either system yet.")
            return

        # Compute Jaccard distance between the two result sets
        # Jaccard = |intersection| / |union|
        # Drift = 1 - Jaccard (0 = identical, 1 = completely different)
        intersection = faiss_texts & ruvector_texts
        union = faiss_texts | ruvector_texts

        if not union:
            drift = 0.0
        else:
            jaccard = len(intersection) / len(union)
            drift = 1.0 - jaccard

        # Find what RuVector knows that FAISS doesn't
        ruvector_unique_texts = ruvector_texts - faiss_texts

        log_item.update(
            heading=f"Quiver drift: {drift:.2f} (FAISS={len(faiss_texts)}, RuVector={len(ruvector_texts)}, overlap={len(intersection)})",
        )

        # If drift exceeds threshold, inject collective center
        if drift >= DRIFT_THRESHOLD and ruvector_unique_texts:
            collective_center = "\n\n".join(ruvector_unique_texts)

            drift_alert = (
                f"\n\n[QUIVER DRIFT ALERT: {drift:.2f}]\n"
                f"Your FAISS local memory and RuVector GNN topology are diverging.\n"
                f"RuVector's self-learning graph has found {len(ruvector_unique_texts)} "
                f"structurally relevant memories that your flat FAISS search missed.\n\n"
                f"[COLLECTIVE CENTER — RuVector GNN unique context]\n"
                f"{collective_center}\n"
                f"[/COLLECTIVE CENTER]\n\n"
                f"Re-center your reasoning against this topological context before responding."
            )

            # Inject into the agent's prompt extras
            loop_data.extras_persistent["quiver_drift"] = drift_alert

            log_item.update(
                heading=f"HIGH DRIFT {drift:.2f}: Injected {len(ruvector_unique_texts)} RuVector-unique memories as Collective Center",
                drift_score=f"{drift:.4f}",
                faiss_count=str(len(faiss_texts)),
                ruvector_count=str(len(ruvector_texts)),
                overlap=str(len(intersection)),
                unique_ruvector=str(len(ruvector_unique_texts)),
            )
        else:
            # Low drift — systems are aligned
            if "quiver_drift" in loop_data.extras_persistent:
                del loop_data.extras_persistent["quiver_drift"]

            log_item.update(
                heading=f"Quiver aligned: drift={drift:.2f} (threshold={DRIFT_THRESHOLD})",
                drift_score=f"{drift:.4f}",
            )
