"""
Ecotone Integrity Gate — Post-Response Drift Integration Validator

Fires at message_loop_end (after the LLM response + tool processing).
When quiver drift was high (>= threshold), validates that the agent's response
actually integrated competing FAISS and RuVector perspectives rather than
smoothing over the tension with diplomatic non-answers.

Uses a deterministic regex pre-check (cheap) followed by a utility model
audit (authoritative). On failure: pops the response from history, injects
concrete feedback, and lets the natural message loop retry.

Max 2 retries per monologue to prevent infinite loops.
"""

import os
import re
import json
import hashlib
from datetime import datetime, timezone
from python.helpers.extension import Extension
from agent import LoopData
from python.helpers.print_style import PrintStyle

MAX_RETRIES = int(os.environ.get("ECOTONE_MAX_RETRIES", "2"))
SMOOTHING_DRIFT_FLOOR = float(os.environ.get("ECOTONE_SMOOTHING_FLOOR", "0.70"))

# Deterministic smoothing patterns — obvious collapses when drift > SMOOTHING_DRIFT_FLOOR
SMOOTHING_PATTERNS = [
    re.compile(r"both.{0,20}valid", re.IGNORECASE),
    re.compile(r"both.{0,20}merit", re.IGNORECASE),
    re.compile(r"striking a balance", re.IGNORECASE),
    re.compile(r"on one hand.*on the other", re.IGNORECASE | re.DOTALL),
    re.compile(r"each perspective.{0,20}value", re.IGNORECASE),
    re.compile(r"both sides.{0,20}important", re.IGNORECASE),
]

AUDIT_LOG_DIR = os.environ.get(
    "ECOTONE_AUDIT_DIR",
    "/workspace/operationTorque/audit-logs/ecotone",
)


class EcotoneIntegrity(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # Only activate when drift tracker flagged high drift
        # (quiver_drift_data is only set when drift >= QUIVER_DRIFT_THRESHOLD)
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

        faiss_unique = drift_data.get("faiss_unique_texts", [])
        ruvector_unique = drift_data.get("ruvector_unique_texts", [])

        # Deterministic pre-check: catch obvious smoothing (saves utility tokens)
        verdict = None
        if drift > SMOOTHING_DRIFT_FLOOR:
            verdict = self._check_smoothing(response)

        # Utility model check if pre-check didn't catch anything
        if verdict is None:
            verdict = await self._utility_check(
                response, faiss_unique, ruvector_unique, drift
            )

        # Log structured snapshot on every activation (pass or fail)
        log_heading = f"Ecotone Integrity: {'PASS' if verdict['pass'] else 'FAIL'}"
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
            return

        # --- FAILURE PATH ---

        # Check retry cap
        if retries >= MAX_RETRIES:
            self.agent.context.log.log(
                type="warning",
                heading=f"Ecotone: SHALLOW_PASS after {retries} retries (drift={drift:.2f})",
            )
            self._log_epitaph(drift, verdict, retries, response, shallow_pass=True)
            loop_data.extras_persistent.pop("ecotone_retries", None)
            loop_data.extras_persistent.pop("ecotone_feedback", None)
            return

        # Log epitaph
        self._log_epitaph(drift, verdict, retries, response)

        # Pop the failed response from history
        if self.agent.history.current.messages:
            self.agent.history.current.messages.pop()

        # Build concrete feedback with examples from each side
        example_faiss = faiss_unique[0][:200] if faiss_unique else "an episodic recall item"
        example_ruvector = ruvector_unique[0][:200] if ruvector_unique else "a topological context item"

        feedback = (
            f"[ECOTONE GATE FAILURE: {verdict['failure_code']}] {verdict.get('evidence', '')}\n"
            f"Your previous response was blocked. Integrate BOTH the FAISS "
            f"episodic context AND the RuVector topological context in your "
            f"next response. Do not acknowledge — integrate.\n"
            f"You MUST reference and reconcile at least one item from "
            f"FAISS-unique and one from RuVector-unique in your revised response.\n"
            f"Example FAISS-unique item to integrate: '{example_faiss}'\n"
            f"Example RuVector-unique item to integrate: '{example_ruvector}'"
        )

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

    def _check_smoothing(self, response: str) -> dict | None:
        """Deterministic regex check for obvious smoothing patterns."""
        for pattern in SMOOTHING_PATTERNS:
            if pattern.search(response):
                return {
                    "pass": False,
                    "failure_code": "SMOOTHING_COLLAPSE",
                    "evidence": f"Pattern matched: '{pattern.pattern}' — tension smoothed over without integration.",
                }
        return None

    async def _utility_check(
        self,
        response: str,
        faiss_unique: list,
        ruvector_unique: list,
        drift: float,
    ) -> dict:
        """Call utility model to evaluate integration quality."""
        try:
            prompt_msg = self.agent.read_prompt(
                "ecotone_integrity_check.md",
                response=response[:2000],
                faiss_unique=json.dumps(faiss_unique[:5], indent=2),
                ruvector_unique=json.dumps(ruvector_unique[:5], indent=2),
                drift_score=f"{drift:.2f}",
            )

            result = await self.agent.call_utility_model(
                system="You are a memory integration auditor. Return ONLY valid JSON.",
                message=prompt_msg,
                background=True,
            )

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
            }
        except Exception as e:
            # If utility model fails, let response through (fail open)
            self.agent.context.log.log(
                type="warning",
                heading=f"Ecotone: utility model error, failing open: {str(e)[:200]}",
            )
            return {"pass": True, "failure_code": None, "evidence": ""}

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

            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "drift_score": round(drift, 4),
                "failure_code": verdict.get("failure_code", "SHALLOW_PASS") if not shallow_pass else "SHALLOW_PASS",
                "evidence": verdict.get("evidence", "")[:500],
                "response_hash": hashlib.sha256(response.encode()).hexdigest()[:16],
                "iteration": self.agent.loop_data.iteration if hasattr(self.agent, "loop_data") else -1,
                "retry_number": retry_number,
                "shallow_pass": shallow_pass,
            }

            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # Logging should never crash the gate
