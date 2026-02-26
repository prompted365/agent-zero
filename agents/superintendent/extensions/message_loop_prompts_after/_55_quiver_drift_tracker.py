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
try:
    from _helpers.naive_bridge import get_surveillance, format_surveillance_injection
except Exception:
    get_surveillance = None
    format_surveillance_injection = None

RUVECTOR_URL = os.environ.get("RUVECTOR_URL", "http://host.docker.internal:6334")
COLLECTION = os.environ.get("RUVECTOR_MOGUL_COLLECTION", "mogul_memory")
PRIORS_COLLECTION = os.environ.get("RUVECTOR_PRIORS_COLLECTION", "civilization_priors")
DRIFT_THRESHOLD = float(os.environ.get("QUIVER_DRIFT_THRESHOLD", "0.60"))
DRIFT_CHECK_INTERVAL = int(os.environ.get("QUIVER_DRIFT_INTERVAL", "1"))
MIN_DRIFT_INTERVAL_SECONDS = float(os.environ.get("QUIVER_DRIFT_MIN_INTERVAL", "30.0"))
TOP_K = 5
CACHE_COSINE_THRESHOLD = 0.15

# Module-level cache — NOT in extras_persistent (avoids 92k char context bloat)
# Survives across loop iterations within the same monologue (same process).
_drift_cache: dict | None = None
_last_drift_time: float = 0.0  # Time-based debounce across monologues


class AnchorTensionTracker(Extension):
    __version__ = "2.3.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "AgentContext.data[quiver_drift_data]; LoopData.extras_persistent[quiver_drift]"

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        import time as _time

        # Clear cache on new monologue (iteration resets to 0 on new user message)
        global _drift_cache, _last_drift_time
        if loop_data.iteration == 0:
            _drift_cache = None

        set = settings.get_settings()
        if not set.get("memory_recall_enabled", True):
            return

        # Only check tension every N iterations
        if loop_data.iteration % DRIFT_CHECK_INTERVAL != 0:
            return

        # Time-based debounce: skip if last check was too recent
        # (prevents excessive processing during hydration/rapid-fire loops)
        now = _time.time()
        if now - _last_drift_time < MIN_DRIFT_INTERVAL_SECONDS and _drift_cache is not None:
            # Re-expose cached data for ecotone gate if available
            if drift_data := (_drift_cache or {}).get("drift_data"):
                if drift_data.get("topic_novelty", 0) >= DRIFT_THRESHOLD:
                    self.agent.context.set_data("quiver_drift_data", drift_data)
            return
        _last_drift_time = now

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
        global _drift_cache
        # Build search query from current context
        user_msg = loop_data.user_message.output_text() if loop_data.user_message else ""
        history = self.agent.history.output_text()[-2000:]
        query = f"{user_msg}\n{history}".strip()

        if not query or len(query) < 10:
            log_item.update(heading="Anchor tension: insufficient context.")
            return

        # Get FAISS memory
        db = await Memory.get(self.agent)

        # Generate embedding for the full query (user + history context) — used for
        # FAISS/RuVector search and inter-store alignment measurement.
        query_embedding = np.array(db.db.embedding_function.embed_query(query[:1000]))

        # Generate separate user-only embedding for query isolation measurement.
        # History dilutes the user message signal — "cruella devil" + 2000 chars of
        # prior verbose output embeds toward the prior conversation, not the absurd input.
        # Isolation must measure the user's ACTUAL input against memory, undiluted.
        user_msg_trimmed = user_msg.strip()[:500]
        if user_msg_trimmed and len(user_msg_trimmed) >= 5:
            user_embedding = np.array(db.db.embedding_function.embed_query(user_msg_trimmed))
        else:
            user_embedding = query_embedding  # Fallback if no user message

        # Check monologue-level cache: if query embedding hasn't shifted
        # significantly, reuse prior FAISS/RuVector results (stores don't
        # change mid-monologue -- sync fires at monologue_end)
        cache = _drift_cache
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
                    self.agent.context.set_data("quiver_drift_data", drift_data)
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

        # Compute FAISS centroid via top-1 proxy (was: re-embed all N results = N calls)
        # Top-1 result is the strongest signal; full centroid adds marginal precision
        # at 5x the embedding cost. Single re-embed preserves semantic alignment measurement.
        if faiss_docs:
            faiss_centroid = np.array(
                db.db.embedding_function.embed_query(faiss_docs[0].page_content[:500])
            )
        else:
            faiss_centroid = query_embedding

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

        # Search civilization_priors (independent divergence reference)
        priors_texts = []
        priors_ids = []
        try:
            priors_payload = {
                "embedding": embedding,
                "top_k": TOP_K,
                "collection": PRIORS_COLLECTION,
            }
            priors_body = json.dumps(priors_payload).encode()
            priors_req = urllib.request.Request(
                f"{RUVECTOR_URL}/search",
                data=priors_body,
                method="POST",
            )
            priors_req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(priors_req, timeout=10) as resp:
                priors_result = json.loads(resp.read().decode())

            for r in priors_result.get("results", []):
                priors_texts.append(r.get("text", "")[:200])
                if r.get("id"):
                    priors_ids.append(str(r["id"]))
        except (urllib.error.URLError, Exception):
            pass  # Priors search is enrichment, not critical path

        # Compute RuVector centroid via top-1 proxy (was: re-embed all N results)
        if ruvector_texts:
            ruvector_centroid = np.array(
                db.db.embedding_function.embed_query(ruvector_texts[0][:500])
            )
        else:
            ruvector_centroid = query_embedding

        # Semantic alignment via cosine similarity of centroids
        if faiss_docs and ruvector_texts:
            dot = float(np.dot(faiss_centroid, ruvector_centroid))
            norm = float(np.linalg.norm(faiss_centroid) * np.linalg.norm(ruvector_centroid) + 1e-9)
            semantic_alignment = max(0.0, min(1.0, dot / norm))
        else:
            semantic_alignment = 1.0  # Only one system available, no divergence measurable

        inter_store_novelty = 1.0 - semantic_alignment

        # Query isolation: how far is the user's ACTUAL input from nearest memory?
        # Uses user_embedding (user message only, no history dilution).
        # When both stores return the same "best guess" for absurd input,
        # inter-store divergence stays low — but query isolation catches it.
        # Low similarity = input is in uncharted territory.
        query_isolation = 0.0
        if faiss_docs:
            q_dot = float(np.dot(user_embedding, faiss_centroid))
            q_norm = float(np.linalg.norm(user_embedding) * np.linalg.norm(faiss_centroid) + 1e-9)
            query_memory_similarity = max(0.0, min(1.0, q_dot / q_norm))
            query_isolation = 1.0 - query_memory_similarity

        # Composite topic novelty: max of inter-store divergence and query isolation.
        # Inter-store divergence catches genuine memory disagreement.
        # Query isolation catches absurd/adversarial inputs both stores handle identically.
        # Scale isolation by 0.9 — input far from any memory IS high novelty,
        # the slight discount prevents single-vector noise from dominating.
        topic_novelty = max(inter_store_novelty, query_isolation * 0.9)

        # Pattern anchors from priors modules via Harpoon pattern scan
        context_text = f"{user_msg}\n{history}"
        pattern_anchors = scan_pattern_anchors(context_text)

        # Naive surveillance: abundance-coupled deviation detection (Bridge 2)
        surveillance_result = None
        surveillance_fn = get_surveillance if get_surveillance is not None else None
        _surv = surveillance_fn() if surveillance_fn else None
        if _surv is not None:
            try:
                surveillance_result = _surv.observe(context_text)
            except Exception:
                pass  # Surveillance is enrichment, not critical path

        # Bridge 3: Ping-pong amplification (cross-reference alerts with Harpoon matches)
        if surveillance_result and surveillance_result.alerts and _surv is not None:
            confirmed_families = {
                a["archetype_family"]
                for a in pattern_anchors
                if "archetype_family" in a
            }
            for alert in surveillance_result.alerts:
                try:
                    _surv.amplify(
                        alert.archetype,
                        alert.archetype in confirmed_families,
                        context_text if alert.archetype in confirmed_families else "",
                    )
                except Exception:
                    pass

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
            "inter_store_novelty": inter_store_novelty,
            "query_isolation": query_isolation,
            "topic_novelty": topic_novelty,
            "pattern_anchors": pattern_anchors,
            "ruvector_neighbors": ruvector_neighbors,
            "faiss_texts": faiss_texts,
            "ruvector_texts": ruvector_texts,
            "retrieved_doc_ids": ruvector_ids,
            "priors_texts": priors_texts,
            "priors_ids": priors_ids,
        }
        if surveillance_result:
            if surveillance_result.alerts:
                drift_data["surveillance_alerts"] = [
                    {
                        "archetype": a.archetype,
                        "z_score": a.z_score,
                        "terms": a.matched_terms,
                        "semantic": a.semantic_matches,
                    }
                    for a in surveillance_result.alerts[:5]
                ]
            if surveillance_result.semantic_scores:
                drift_data["semantic_scores"] = surveillance_result.semantic_scores
            if surveillance_result.cumulative_drifts:
                drift_data["cumulative_drifts"] = [
                    {"archetype": d.archetype, "integral": d.integral, "trend": d.trend}
                    for d in surveillance_result.cumulative_drifts[:3]
                ]

        if topic_novelty >= DRIFT_THRESHOLD:
            self.agent.context.set_data("quiver_drift_data", drift_data)
        else:
            self.agent.context.set_data("quiver_drift_data", None)

        # Cache results + embedding for subsequent iterations in this monologue
        # If RuVector failed, mark cache so next iteration retries instead of serving stale data
        _drift_cache = {
            "query_embedding": embedding,
            "drift_data": drift_data,
            "ruvector_failed": ruvector_failed,
        }

        surv_count = len(surveillance_result.alerts) if surveillance_result else 0
        log_item.update(
            heading=(
                f"Anchor tension: {topic_novelty:.2f} "
                f"(stores={inter_store_novelty:.2f}, isolation={query_isolation:.2f}, "
                f"FAISS={len(faiss_texts)}, RuVector={len(ruvector_texts)}, "
                f"anchors={len(pattern_anchors)}, surv_alerts={surv_count})"
            ),
        )

        # Build compact injection blocks — every char here costs tokens
        injection_parts = []

        if topic_novelty >= DRIFT_THRESHOLD and ruvector_texts:
            # Compact structural context — 80-char snippets, top 3 only
            structural_items = ruvector_neighbors[:3] if ruvector_neighbors else ruvector_texts[:3]
            structural_text = "\n".join(f"  - {item[:80]}" for item in structural_items)

            tension_source = (
                "store divergence" if inter_store_novelty >= query_isolation * 0.85
                else "query isolation"
            )
            injection_parts.append(
                f"\n\n[ANCHOR TENSION: {topic_novelty:.2f} \u2014 {tension_source}]\n"
                f"stores={semantic_alignment:.2f} isolation={query_isolation:.2f}\n"
                f"[STRUCTURAL]\n{structural_text}\n[/STRUCTURAL]"
            )

        # Compact priors — top 3, 80-char snippets
        if priors_texts and topic_novelty >= DRIFT_THRESHOLD:
            priors_items = "\n".join(f"  - {item[:80]}" for item in priors_texts[:3])
            injection_parts.append(
                f"\n[PRIORS]\n{priors_items}\n[/PRIORS]"
            )

        # Compact pattern resonance — term + archetype only
        if pattern_anchors:
            anchor_lines = []
            for a in pattern_anchors[:5]:
                shape_tag = ""
                if "archetype_family" in a:
                    shape_tag = f" \u2192 {a['archetype_family']}"
                anchor_lines.append(f'  - "{a["term"]}"{shape_tag}')
            resonance_text = "\n".join(anchor_lines)

            families = sorted({
                a["archetype_family"]
                for a in pattern_anchors
                if "archetype_family" in a
            })
            chord_note = ""
            if len(families) >= 2:
                chord_note = f"\nCHORD: {', '.join(families)}"

            injection_parts.append(
                f"\n[RESONANCE] {len(pattern_anchors)} patterns:\n"
                f"{resonance_text}{chord_note}\n[/RESONANCE]"
            )

        # Compact surveillance — inline summary, no verbose explanation
        if surveillance_result and (surveillance_result.alerts or surveillance_result.cumulative_drifts):
            confirmed_families = {
                a["archetype_family"]
                for a in pattern_anchors
                if "archetype_family" in a
            }
            surv_lines = []
            if surveillance_result.alerts:
                for alert in surveillance_result.alerts[:3]:
                    tag = " [CONFIRMED]" if alert.archetype in confirmed_families else ""
                    surv_lines.append(f"  - {alert.archetype}: z={alert.z_score:.1f}\u03c3{tag}")
            if surveillance_result.cumulative_drifts:
                for d in surveillance_result.cumulative_drifts[:2]:
                    arrow = "\u2197" if d.trend > 0.01 else ("\u2198" if d.trend < -0.01 else "\u2192")
                    surv_lines.append(f"  - drift:{d.archetype} {arrow} int={d.integral:.2f}")
            if surv_lines:
                injection_parts.append(
                    f"\n[SURVEILLANCE]\n" + "\n".join(surv_lines) + "\n[/SURVEILLANCE]"
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
