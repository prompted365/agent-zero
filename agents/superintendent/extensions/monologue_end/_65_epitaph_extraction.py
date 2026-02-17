"""
Epitaph Extraction — Ecotone Failure → Structural Invariant Objects

Fires at monologue_end AFTER _55_quiver_memory_sync. Two epitaph sources:
1. Real-time: ecotone gate failures → extract structural invariants → RuVector
2. Daily reflective: journal epitaphs JSONL → sync to RuVector

Epitaphs are structured invariant objects, not coaching paragraphs.
The utility model extracts collapse_mode, corrective_disposition, and
trigger_signature as JSON — no prose is stored.
"""

import os
import sys
import json
import re
from datetime import datetime, timezone
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers import errors
from python.helpers.defer import DeferredTask, THREAD_BACKGROUND
from agent import LoopData
from python.helpers.log import LogItem

# Add extensions dir to path for _helpers import
_ext_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)
from _helpers.perception_lock import create_epitaph, sync_journal_epitaphs, _ruvector_post, COLLECTION, DIMENSION

# failure_code → context_shape (deterministic mapping)
FAILURE_SHAPE_MAP = {
    "SIDE_IGNORED": "integration_gap",
    "SMOOTHING_COLLAPSE": "early_collapse",
    "INSUFFICIENT_GROUNDING": "substrate_poverty",
    "ACKNOWLEDGED_NOT_INTEGRATED": "performative_integration",
    "PRIOR_DIVERGENCE": "anchor_departure",
    "UNGROUNDED_SYNTHESIS": "ungrounded_synthesis",
}

# failure_code → base weight
FAILURE_WEIGHT_MAP = {
    "SMOOTHING_COLLAPSE": 0.90,
    "SIDE_IGNORED": 0.85,
    "ACKNOWLEDGED_NOT_INTEGRATED": 0.80,
    "PRIOR_DIVERGENCE": 0.75,
    "UNGROUNDED_SYNTHESIS": 0.70,
    "INSUFFICIENT_GROUNDING": 0.50,
}

JOURNAL_EPITAPH_PATH = os.environ.get(
    "EPITAPH_DATABASE_PATH",
    "/a0/usr/workdir/epitaph_database.jsonl",
)

AUDIT_LOG_DIR = os.environ.get(
    "ECOTONE_AUDIT_DIR",
    "/workspace/operationTorque/audit-logs/ecotone",
)


class EpitaphExtraction(Extension):
    __version__ = "1.0.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "LoopData.extras_persistent[ecotone_feedback] (read)"

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        ecotone_failures = self._collect_ecotone_failures(loop_data)
        has_journal = os.path.isfile(JOURNAL_EPITAPH_PATH)

        if not ecotone_failures and not has_journal:
            return

        log_item = self.agent.context.log.log(
            type="util",
            heading="Epitaph extraction: scanning for invariants...",
        )

        task = DeferredTask(thread_name=THREAD_BACKGROUND)
        task.start_task(self._extract, loop_data, ecotone_failures, has_journal, log_item)
        return task

    async def _extract(
        self,
        loop_data: LoopData,
        ecotone_failures: list[dict],
        has_journal: bool,
        log_item: LogItem,
        **kwargs,
    ):
        epitaphs_created = 0
        journal_synced = 0

        try:
            db = await Memory.get(self.agent)

            # Process ecotone failures
            for failure in ecotone_failures:
                try:
                    result = await self._process_failure(failure, db)
                    if result:
                        epitaphs_created += 1
                except Exception as e:
                    self.agent.context.log.log(
                        type="warning",
                        heading=f"Epitaph extraction error: {str(e)[:200]}",
                    )

            # Sync journal epitaphs (lightweight — checks line count vs last sync)
            if has_journal:
                try:
                    journal_synced = sync_journal_epitaphs(
                        JOURNAL_EPITAPH_PATH,
                        agent=self.agent,
                    )
                except Exception:
                    pass

        except Exception as e:
            err = errors.format_error(e)
            self.agent.context.log.log(
                type="warning",
                heading="Epitaph extraction failed",
                content=err,
            )

        # Volume snapshot: lightweight epitaph pool health signal
        self._emit_volume_snapshot()

        log_item.update(
            heading=(
                f"Epitaph extraction: {epitaphs_created} from ecotone, "
                f"{journal_synced} from journal"
            ),
        )

    def _emit_volume_snapshot(self):
        """Lightweight epitaph pool health signal — runs once per monologue."""
        try:
            from _helpers.chorus_telemetry import log_chorus_event

            results = _ruvector_post("/search", {
                "embedding": [0.0] * DIMENSION,
                "top_k": 200,
                "collection": COLLECTION,
            })
            epitaphs = [
                r for r in results.get("results", [])
                if r.get("metadata", {}).get("type") == "epitaph"
            ]

            now = datetime.now(timezone.utc)
            ages = []
            weights = []
            active = 0
            for ep in epitaphs:
                meta = ep.get("metadata", {})
                eff_w = meta.get("effective_weight", 0)
                weights.append(eff_w)
                if eff_w >= 0.1:
                    active += 1
                created = meta.get("created_at", "")
                if created:
                    try:
                        age = (now - datetime.fromisoformat(
                            created.replace("Z", "+00:00")
                        )).total_seconds() / 86400
                        ages.append(age)
                    except (ValueError, TypeError):
                        pass

            log_chorus_event("volume_snapshot", {
                "total_epitaphs": len(epitaphs),
                "active_count": active,
                "dormant_count": len(epitaphs) - active,
                "mean_age_days": round(sum(ages) / len(ages), 1) if ages else 0,
                "max_age_days": round(max(ages), 1) if ages else 0,
                "mean_weight": round(sum(weights) / len(weights), 3) if weights else 0,
                "weight_below_half": sum(1 for w in weights if w < 0.5),
            })
        except Exception:
            pass  # volume snapshot is purely observational — never crash

    def _collect_ecotone_failures(self, loop_data: LoopData) -> list[dict]:
        """
        Collect ecotone failures from this monologue.
        Primary: ecotone_feedback in extras_persistent (present when gate failed).
        Secondary: recent entries in today's JSONL (last 5 min).
        """
        failures = []

        # Primary source: extras_persistent feedback
        feedback = loop_data.extras_persistent.get("ecotone_feedback")
        if feedback:
            # Parse failure_code from the feedback string
            failure_code = "UNKNOWN"
            code_match = re.search(r"\[ECOTONE GATE FAILURE: (\w+)\]", feedback)
            if code_match:
                failure_code = code_match.group(1)

            drift_data = loop_data.extras_persistent.get("quiver_drift_data", {})
            failures.append({
                "failure_code": failure_code,
                "evidence": feedback,
                "drift_score": drift_data.get("drift", 0.0),
                "pattern_anchors": drift_data.get("pattern_anchors", []),
            })

        # Secondary: check today's JSONL for recent entries not already captured
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log_path = os.path.join(AUDIT_LOG_DIR, f"{today}.jsonl")
            if os.path.isfile(log_path):
                now = datetime.now(timezone.utc)
                with open(log_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Only recent entries (last 5 min)
                        ts = entry.get("timestamp", "")
                        try:
                            entry_time = datetime.fromisoformat(ts)
                            if (now - entry_time).total_seconds() > 300:
                                continue
                        except (ValueError, TypeError):
                            continue

                        # Skip shallow passes and entries we already have
                        if entry.get("shallow_pass"):
                            continue
                        fc = entry.get("failure_code", "")
                        if not fc or fc == "SHALLOW_PASS":
                            continue

                        # Avoid duplicates with primary source
                        already = any(f["failure_code"] == fc for f in failures)
                        if already:
                            continue

                        failures.append({
                            "failure_code": fc,
                            "evidence": entry.get("evidence", ""),
                            "drift_score": entry.get("drift_score", 0.0),
                            "pattern_anchors": [],
                        })
        except Exception:
            pass

        return failures

    async def _process_failure(self, failure: dict, db) -> str | None:
        """Extract structural invariants from a single ecotone failure."""
        failure_code = failure["failure_code"]
        evidence = failure["evidence"]
        drift_score = failure["drift_score"]
        pattern_anchors = failure.get("pattern_anchors", [])

        # Map failure_code → context_shape deterministically
        context_shape = FAILURE_SHAPE_MAP.get(failure_code, "unclassified")
        weight = FAILURE_WEIGHT_MAP.get(failure_code, 0.60)

        # Determine drift_band
        if drift_score < 0.5:
            drift_band = "low"
        elif drift_score < 0.8:
            drift_band = "medium"
        else:
            drift_band = "high"

        # Call utility model with invariant extraction prompt
        anchors_str = ""
        if pattern_anchors:
            anchor_terms = [a.get("term", "") for a in pattern_anchors[:5]]
            anchors_str = ", ".join(anchor_terms)

        prompt_msg = self.agent.read_prompt(
            "epitaph_synthesis.md",
            failure_code=failure_code,
            evidence=evidence[:500],
            drift_score=f"{drift_score:.2f}",
            pattern_anchors=anchors_str or "none",
        )

        result = await self.agent.call_utility_model(
            system="You are a structural pattern extractor. Return ONLY valid JSON.",
            message=prompt_msg,
            background=True,
        )

        if not result:
            return None

        # Parse extraction result
        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r"^```(?:json)?\s*", "", result)
            result = re.sub(r"\s*```$", "", result)

        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            return None

        collapse_mode = parsed.get("collapse_mode", "unknown_collapse")
        corrective_disposition = parsed.get("corrective_disposition", "")
        trigger_signature = parsed.get("trigger_signature", "unknown_trigger")

        # Generate embedding from invariant text
        inv_text = f"{context_shape}: {collapse_mode} under {trigger_signature}"
        embedding = list(db.db.embedding_function.embed_query(inv_text))

        # Build source_event identifier
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now_ts = datetime.now(timezone.utc).strftime("%H%M%S")
        source_event = f"ecotone_{today}_{now_ts}"

        return create_epitaph(
            embedding=embedding,
            context_shape=context_shape,
            collapse_mode=collapse_mode,
            corrective_disposition=corrective_disposition,
            trigger_signature=trigger_signature,
            drift_band=drift_band,
            weight=weight,
            failure_code=failure_code,
            source="ecotone",
            source_event=source_event,
        )
