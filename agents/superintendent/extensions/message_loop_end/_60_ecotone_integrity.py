"""
Ecotone Integrity Gate — Post-Response Anchor Tension Integration Validator

Fires at message_loop_end (after the LLM response + tool processing).
When anchor tension was high (>= threshold), validates that the agent's response
actually integrated competing FAISS and RuVector perspectives rather than
smoothing over the tension with diplomatic non-answers.

Validation layers (in order):
1. INSUFFICIENT_GROUNDING check — if memory substrate is all system-meta, flag
   the gap rather than penalizing the response for lacking integration material.
2. Deterministic regex pre-check (cheap) — catch obvious smoothing collapses.
3. Utility model audit (authoritative) — evaluates integration quality + prior
   divergence when civilization priors are available.

On failure: pops the response from history, injects concrete feedback, and lets
the natural message loop retry. Max 2 retries per monologue.
"""

import os
import sys
import re
import json
import hashlib
from datetime import datetime, timezone
from python.helpers.extension import Extension
from agent import LoopData
from python.helpers.print_style import PrintStyle

# Add extensions dir to path for _helpers import
_ext_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)
from _helpers.perception_lock import decay_epitaph

MAX_RETRIES = int(os.environ.get("ECOTONE_MAX_RETRIES", "2"))
SMOOTHING_DRIFT_FLOOR = float(os.environ.get("ECOTONE_SMOOTHING_FLOOR", "0.70"))
GROUNDING_META_THRESHOLD = float(os.environ.get("ECOTONE_META_THRESHOLD", "0.80"))

# Keywords indicating system-meta content (architecture docs, not domain substance)
SYSTEM_META_KEYWORDS = [
    "extension", "ecotone", "drift_tracker", "faiss", "ruvector",
    "quiver", "memory_sync", "monologue_end", "message_loop",
    "collective center", "extras_persistent", "loop_data",
    "agent.system.tool", "superintendent", "harpoon", "boris_strike",
    "ghost_chorus", "epitaph", "perception_lock", "coaching",
    "corrective_disposition",
]

# Deterministic smoothing patterns — obvious collapses when drift > SMOOTHING_DRIFT_FLOOR
SMOOTHING_PATTERNS = [
    re.compile(r"both.{0,20}valid", re.IGNORECASE),
    re.compile(r"both.{0,20}merit", re.IGNORECASE),
    re.compile(r"striking a balance", re.IGNORECASE),
    re.compile(r"on one hand.{0,500}on the other", re.IGNORECASE),
    re.compile(r"each perspective.{0,20}value", re.IGNORECASE),
    re.compile(r"both sides.{0,20}important", re.IGNORECASE),
]

# Patterns to strip before running smoothing regex (non-prose content)
# NOTE: Lazy match handles simple fences; truly nested fences (``` inside ```)
# would require iterative stripping, but Mogul responses use JSON wire protocol
# so nested raw markdown fences are not observed in practice.
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_JSON_BLOCK_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")

AUDIT_LOG_DIR = os.environ.get(
    "ECOTONE_AUDIT_DIR",
    "/workspace/operationTorque/audit-logs/ecotone",
)


class EcotoneIntegrity(Extension):
    __version__ = "1.1.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "LoopData.extras_persistent[quiver_drift_data, ecotone_retries, ecotone_feedback]"

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # Only activate when tension tracker flagged high tension
        # (quiver_drift_data is only set when topic_novelty >= QUIVER_DRIFT_THRESHOLD)
        drift_data = loop_data.extras_persistent.get("quiver_drift_data")
        if not drift_data:
            return

        drift = drift_data["drift"]

        # Skip tool-use iterations — no natural language to evaluate
        response = loop_data.last_response or ""
        if not response or self._is_tool_response(response):
            return

        # Initialize retry counter
        retries = loop_data.extras_persistent.get("ecotone_retries", 0)

        faiss_unique = drift_data.get("faiss_texts", [])
        ruvector_unique = drift_data.get("ruvector_texts", [])
        priors_unique = drift_data.get("pattern_anchors", [])

        # Layer 1: Check for insufficient grounding (system-meta-only substrate)
        verdict = self._check_grounding(faiss_unique, ruvector_unique)

        # Layer 2: Deterministic pre-check for smoothing (saves utility tokens)
        if verdict is None and drift > SMOOTHING_DRIFT_FLOOR:
            verdict = self._check_smoothing(response)

        # Layer 3: Utility model check (integration quality + prior divergence)
        if verdict is None:
            verdict = await self._utility_check(
                response, faiss_unique, ruvector_unique, drift,
                priors_unique=priors_unique,
            )

        # Log structured snapshot on every activation (pass or fail)
        log_heading = f"Ecotone Integrity: {'PASS' if verdict['pass'] else 'FAIL'} (tension={drift:.2f})"
        if not verdict["pass"]:
            log_heading += f" [{verdict['failure_code']}]"

        self.agent.context.log.log(
            type="util",
            heading=log_heading,
            drift_score=f"{drift:.4f}",
            failure_code=verdict.get("failure_code", ""),
            evidence=verdict.get("evidence", "")[:300],
            retry_number=str(retries),
        )

        if verdict["pass"]:
            # Reset retry counter on success
            loop_data.extras_persistent.pop("ecotone_retries", None)
            loop_data.extras_persistent.pop("ecotone_feedback", None)

            # Decay epitaphs that contributed to this successful response
            chorus_ids = loop_data.extras_persistent.get("_chorus_epitaph_ids", [])
            if chorus_ids:
                for eid in chorus_ids:
                    try:
                        decay_epitaph(eid)
                    except Exception:
                        pass
                loop_data.extras_persistent.pop("_chorus_epitaph_ids", None)

            # Telemetry: chorus_outcome (pass)
            try:
                from _helpers.chorus_telemetry import log_chorus_event
                log_chorus_event("chorus_outcome", {
                    "chorus_was_active": bool(loop_data.extras_persistent.get("ghost_chorus")),
                    "epitaph_ids": chorus_ids,
                    "gate_result": "pass",
                    "failure_code": None,
                    "drift_score": round(drift, 4),
                })
            except Exception:
                pass

            return

        # --- FAILURE PATH ---

        # Check retry cap
        if retries >= MAX_RETRIES:
            self.agent.context.log.log(
                type="warning",
                heading=f"Ecotone: SHALLOW_PASS after {retries} retries (drift={drift:.2f})",
            )
            self._log_epitaph(drift, verdict, retries, response, shallow_pass=True)
            # Telemetry: chorus_outcome (shallow_pass)
            try:
                from _helpers.chorus_telemetry import log_chorus_event
                log_chorus_event("chorus_outcome", {
                    "chorus_was_active": bool(loop_data.extras_persistent.get("ghost_chorus")),
                    "epitaph_ids": loop_data.extras_persistent.get("_chorus_epitaph_ids", []),
                    "gate_result": "shallow_pass",
                    "failure_code": "SHALLOW_PASS",
                    "drift_score": round(drift, 4),
                })
            except Exception:
                pass
            loop_data.extras_persistent.pop("ecotone_retries", None)
            loop_data.extras_persistent.pop("ecotone_feedback", None)
            return

        # Log epitaph
        self._log_epitaph(drift, verdict, retries, response)

        # Telemetry: chorus_outcome (fail)
        try:
            from _helpers.chorus_telemetry import log_chorus_event
            log_chorus_event("chorus_outcome", {
                "chorus_was_active": bool(loop_data.extras_persistent.get("ghost_chorus")),
                "epitaph_ids": loop_data.extras_persistent.get("_chorus_epitaph_ids", []),
                "gate_result": "fail",
                "failure_code": verdict.get("failure_code"),
                "drift_score": round(drift, 4),
            })
        except Exception:
            pass

        # Pop the failed response from history
        if self.agent.history.current.messages:
            self.agent.history.current.messages.pop()

        # Build concrete feedback with examples from each side
        example_faiss = faiss_unique[0][:200] if faiss_unique else "an episodic recall item"
        example_ruvector = ruvector_unique[0][:200] if ruvector_unique else "a topological context item"

        feedback = (
            f"[ECOTONE GATE FAILURE: {verdict['failure_code']}] {verdict.get('evidence', '')}\n"
            f"Your previous response was blocked. You must ENGAGE with the "
            f"divergent memory context — not reconcile it, but analyze it.\n"
            f"For each unique item, categorize it: undiscovered, stale, "
            f"parallel-valid, noise, or actionable gap. Use what's relevant.\n"
            f"Example FAISS-unique item: '{example_faiss}'\n"
            f"Example RuVector-unique item: '{example_ruvector}'"
        )

        pattern_anchors = drift_data.get("pattern_anchors", [])
        if pattern_anchors:
            anchor_terms = [a["term"] for a in pattern_anchors[:5]]
            feedback += f"\nPattern resonance detected: {', '.join(anchor_terms)}. Consider how these civilization patterns relate to your response."

        loop_data.extras_persistent["ecotone_feedback"] = feedback
        loop_data.extras_persistent["ecotone_retries"] = retries + 1

        PrintStyle(font_color="orange", padding=True).print(
            f"Ecotone gate blocked response: {verdict['failure_code']} (retry {retries + 1}/{MAX_RETRIES})"
        )

    def _is_tool_response(self, response: str) -> bool:
        """Check if response is primarily a tool call (no natural language to evaluate)."""
        stripped = response.strip()
        # Tool calls in Agent Zero are JSON with tool_name/tool_args
        if stripped.startswith("{") and '"tool_name"' in stripped:
            return True
        # Also skip very short responses (likely partial/streaming artifacts)
        if len(stripped) < 50:
            return True
        return False

    def _check_grounding(self, faiss_unique: list, ruvector_unique: list) -> dict | None:
        """Check if memory substrate is all system-meta (no domain substance)."""
        all_texts = faiss_unique + ruvector_unique
        if not all_texts:
            return {
                "pass": False,
                "failure_code": "INSUFFICIENT_GROUNDING",
                "evidence": "Both memory systems returned empty unique texts — no substrate to integrate.",
                "check_type": "grounding_check",
            }

        meta_count = 0
        for text in all_texts:
            text_lower = text.lower()
            if any(kw in text_lower for kw in SYSTEM_META_KEYWORDS):
                meta_count += 1

        meta_ratio = meta_count / len(all_texts)
        if meta_ratio >= GROUNDING_META_THRESHOLD:
            return {
                "pass": False,
                "failure_code": "INSUFFICIENT_GROUNDING",
                "evidence": (
                    f"{meta_count}/{len(all_texts)} unique texts ({meta_ratio:.0%}) are system-meta content. "
                    f"No domain-relevant substrate available for integration."
                ),
                "check_type": "grounding_check",
            }
        return None

    def _check_smoothing(self, response: str) -> dict | None:
        """Deterministic regex check for obvious smoothing patterns.
        Strips code fences and JSON blocks before matching — only checks prose."""
        # Strip non-prose content to avoid false positives
        prose = _CODE_FENCE_RE.sub("", response)
        prose = _JSON_BLOCK_RE.sub("", prose)

        for pattern in SMOOTHING_PATTERNS:
            if pattern.search(prose):
                return {
                    "pass": False,
                    "failure_code": "SMOOTHING_COLLAPSE",
                    "evidence": f"Pattern matched: '{pattern.pattern}' — tension smoothed over without integration.",
                    "check_type": "regex_precheck",
                }
        return None

    async def _utility_check(
        self,
        response: str,
        faiss_unique: list,
        ruvector_unique: list,
        drift: float,
        priors_unique: list | None = None,
    ) -> dict:
        """Call utility model to evaluate integration quality and prior divergence."""
        try:
            priors_json = json.dumps(priors_unique[:5], indent=2) if priors_unique else "[]"

            prompt_msg = self.agent.read_prompt(
                "ecotone_integrity_check.md",
                response=response[:2000],
                faiss_unique=json.dumps(faiss_unique[:5], indent=2),
                ruvector_unique=json.dumps(ruvector_unique[:5], indent=2),
                priors_unique=priors_json,
                drift_score=f"{drift:.2f}",
            )

            result = await self.agent.call_utility_model(
                system="You are a memory integration auditor. Return ONLY valid JSON.",
                message=prompt_msg,
                background=True,
            )

            # Guard against None from utility model
            if result is None:
                return {"pass": True, "failure_code": None, "evidence": "utility model returned None", "check_type": "utility_model"}
            # Parse JSON from response
            result = result.strip()
            # Handle markdown code fences
            if result.startswith("```"):
                result = re.sub(r"^```(?:json)?\s*", "", result)
                result = re.sub(r"\s*```$", "", result)

            parsed = json.loads(result)
            return {
                "pass": parsed.get("pass", True),
                "failure_code": parsed.get("failure_code"),
                "evidence": parsed.get("evidence", ""),
                "check_type": "utility_model",
            }
        except Exception as e:
            # If utility model fails, let response through (fail open)
            self.agent.context.log.log(
                type="warning",
                heading=f"Ecotone: utility model error, failing open: {str(e)[:200]}",
            )
            return {"pass": True, "failure_code": None, "evidence": "", "check_type": "utility_model"}

    def _log_epitaph(
        self,
        drift: float,
        verdict: dict,
        retry_number: int,
        response: str,
        shallow_pass: bool = False,
    ):
        """Write failure epitaph to JSONL audit log."""
        try:
            os.makedirs(AUDIT_LOG_DIR, exist_ok=True)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log_path = os.path.join(AUDIT_LOG_DIR, f"{today}.jsonl")

            iteration = self.agent.loop_data.iteration if hasattr(self.agent, "loop_data") else -1
            cadence_phases = ["Design", "Implement", "Verify", "Evolve"]

            # Count pattern anchors from drift data if available
            drift_data = self.agent.loop_data.extras_persistent.get("quiver_drift_data", {}) if hasattr(self.agent, "loop_data") else {}
            pattern_anchor_count = len(drift_data.get("pattern_anchors", []))

            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "drift_score": round(drift, 4),
                "failure_code": verdict.get("failure_code", "SHALLOW_PASS") if not shallow_pass else "SHALLOW_PASS",
                "check_type": verdict.get("check_type", "unknown"),
                "evidence": verdict.get("evidence", "")[:500],
                "response_hash": hashlib.sha256(response.encode()).hexdigest()[:16],
                "iteration": iteration,
                "retry_number": retry_number,
                "shallow_pass": shallow_pass,
                "pattern_anchors": pattern_anchor_count,
                "cadence_beat": (iteration % 4) + 1 if iteration >= 0 else None,
                "cadence_measure": (iteration // 4) + 1 if iteration >= 0 else None,
                "cadence_phase": cadence_phases[iteration % 4] if iteration >= 0 else None,
                "chorus_active": bool(self.agent.loop_data.extras_persistent.get("ghost_chorus")) if hasattr(self.agent, "loop_data") else False,
                "chorus_epitaph_count": len(self.agent.loop_data.extras_persistent.get("_chorus_epitaph_ids", [])) if hasattr(self.agent, "loop_data") else 0,
            }

            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            # Fail-open: log the error but never crash the gate
            try:
                self.agent.context.log.log(
                    type="warning",
                    heading=f"Ecotone: epitaph logging failed: {str(e)[:200]}",
                )
            except Exception:
                pass
