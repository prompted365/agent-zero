"""
Ghost Chorus — Ambient Posture Injection from Structural Invariants

Fires at message_loop_prompts_after (_45, BEFORE drift tracker _55 and
recall_memories _50). Coaching shapes context before drift measurement.

Design principle: The chorus works the way effective coaching works — it
centers context and lets the reasoning arrive, rather than delivering
conclusions. It never instructs. It never references its source material.
It shapes the landscape of consideration so that the agent naturally
navigates better.

The test: If Mogul's response after chorus injection contains language like
"as past contexts suggest" or references the coaching explicitly — the
chorus has failed. The chorus is correct when Mogul simply reasons more
stably without attribution.
"""

import os
import sys
import re
from python.helpers.extension import Extension
from python.helpers.memory import Memory
from python.helpers import errors, settings
from agent import LoopData

# Add extensions dir to path for _helpers import
_ext_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)
from _helpers.perception_lock import retrieve_coaching_epitaphs

# Context shape detection keywords
_CONVERGING_KEYWORDS = re.compile(
    r"(on one hand|trade.?off|versus|competing|tension between|balance between"
    r"|both .{0,20} and|either .{0,30} or)",
    re.IGNORECASE,
)
_IDENTITY_KEYWORDS = re.compile(
    r"(who (?:am|are) |identity|role|scope|boundary|rename|rebrand"
    r"|called|naming|persona)",
    re.IGNORECASE,
)

# Intensity calibration: chorus_mode → (max_epitaphs, synthesis_mode)
# chorus_mode is an operational state separate from epitaph context_shape archetypes.
INTENSITY_MAP = {
    "steady_state": (0, "none"),
    "novel_territory": (1, "brief"),
    "under_pressure": (1, "supportive"),
    "recovery_attempt": (2, "targeted"),
    "converging_constraints": (3, "full"),
    "identity_pressure": (3, "full"),
}


class GhostChorus(Extension):
    __version__ = "1.0.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "LoopData.extras_persistent[ghost_chorus, _chorus_epitaph_ids] (write)"

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        set = settings.get_settings()
        if not set.get("memory_recall_enabled", True):
            return

        # Step 1: Chorus mode detection (deterministic, no model call)
        # chorus_mode is operational state; distinct from epitaph context_shape archetypes
        chorus_mode = self._detect_chorus_mode(loop_data)

        if chorus_mode == "steady_state":
            # Chorus is silent when smooth
            loop_data.extras_persistent.pop("ghost_chorus", None)
            loop_data.extras_persistent.pop("_chorus_epitaph_ids", None)
            # Telemetry: sample 10% of silence events to avoid flooding
            import random
            if random.random() < 0.1:
                try:
                    from _helpers.chorus_telemetry import log_chorus_event
                    log_chorus_event("chorus_silence", {
                        "chorus_mode": "steady_state",
                        "reason": "default",
                    })
                except Exception:
                    pass
            return

        max_epitaphs, synthesis_mode = INTENSITY_MAP.get(
            chorus_mode, (1, "brief")
        )

        # Step 2: Epitaph retrieval
        try:
            db = await Memory.get(self.agent)
        except Exception:
            return

        # Build query from current context (cap at 1000 chars)
        user_msg = loop_data.user_message.output_text() if loop_data.user_message else ""
        query = user_msg[:1000]
        if not query:
            return

        try:
            embedding = list(db.db.embedding_function.embed_query(query))
        except Exception:
            return

        # Pass chorus_mode as context_shape for shape-match bonus on overlapping values
        # (novel_territory, converging_constraints, identity_pressure exist in both vocabularies)
        epitaphs = retrieve_coaching_epitaphs(
            embedding=embedding,
            context_shape=chorus_mode,
            top_k=max_epitaphs,
        )

        if not epitaphs:
            # Correct for early days — nothing to say yet
            try:
                from _helpers.chorus_telemetry import log_chorus_event
                log_chorus_event("chorus_silence", {
                    "chorus_mode": chorus_mode,
                    "reason": "no_epitaphs",
                })
            except Exception:
                pass
            return

        log_item = self.agent.context.log.log(
            type="util",
            heading=f"Ghost Chorus: {chorus_mode} — {len(epitaphs)} epitaphs retrieved",
        )

        # Step 3: Build invariants block for synthesis prompt
        invariants_lines = []
        for i, ep in enumerate(epitaphs, 1):
            invariants_lines.append(
                f"{i}. collapse_mode: {ep['collapse_mode']} | "
                f"corrective: {ep['corrective_disposition']} | "
                f"trigger: {ep['trigger_signature']} | "
                f"seen {ep['recurrence_count']} times"
            )
        invariants_block = "\n".join(invariants_lines)

        # Determine drift band from cached drift data
        drift_data = loop_data.extras_persistent.get("_drift_cache", {})
        dd = drift_data.get("drift_data", {})
        topic_novelty = dd.get("topic_novelty", 0.0)
        if topic_novelty >= 0.8:
            drift_band = "high"
        elif topic_novelty >= 0.5:
            drift_band = "medium"
        else:
            drift_band = "low"

        # Build pattern anchors section if available
        pattern_anchors = dd.get("pattern_anchors", [])
        pattern_section = ""
        if pattern_anchors:
            anchor_terms = [a.get("term", "") for a in pattern_anchors[:5]]
            pattern_section = f"Active pattern anchors: {', '.join(anchor_terms)}"

        # Step 4: Coaching synthesis via utility model
        prompt_msg = self.agent.read_prompt(
            "ghost_chorus_synthesis.md",
            context_shape=chorus_mode,
            drift_band=drift_band,
            pattern_anchors_section=pattern_section,
            invariants_block=invariants_block,
        )

        try:
            coaching = await self.agent.call_utility_model(
                system="You are generating ambient context awareness. No markers, no attribution, no self-reference.",
                message=prompt_msg,
                background=True,
            )
        except Exception:
            return

        if not coaching or not coaching.strip():
            return

        coaching = coaching.strip()

        # Step 5: Injection — write to extras_persistent
        # The [GHOST CHORUS] tags are for the extras_persistent key boundary only
        loop_data.extras_persistent["ghost_chorus"] = coaching
        loop_data.extras_persistent["_chorus_epitaph_ids"] = [
            ep["id"] for ep in epitaphs if ep.get("id")
        ]

        # Telemetry: chorus_activation
        try:
            from _helpers.chorus_telemetry import log_chorus_event
            log_chorus_event("chorus_activation", {
                "chorus_mode": chorus_mode,
                "epitaph_ids": [ep["id"] for ep in epitaphs if ep.get("id")],
                "epitaph_ages": [ep.get("age_days", 0) for ep in epitaphs],
                "epitaph_weights": [ep.get("effective_weight", 0) for ep in epitaphs],
                "hypothetical_age_weights": [ep.get("hypothetical_age_weight", 0) for ep in epitaphs],
                "drift_band": drift_band,
                "synthesis_length": len(coaching),
                "topic_novelty": topic_novelty,
                "pattern_anchor_count": len(pattern_anchors),
            })
        except Exception:
            pass

        log_item.update(
            heading=(
                f"Ghost Chorus [{chorus_mode}]: injected {len(epitaphs)} dispositions "
                f"(drift_band={drift_band})"
            ),
        )

    def _detect_chorus_mode(self, loop_data: LoopData) -> str:
        """
        Deterministic chorus mode detection. No model call.
        Priority order matters — most specific wins.
        Chorus mode is an operational state, distinct from epitaph context_shape archetypes.
        """
        extras = loop_data.extras_persistent

        # Recovery attempt: ecotone just failed
        if extras.get("ecotone_feedback"):
            return "recovery_attempt"

        # Under pressure: retries in progress
        retries = extras.get("ecotone_retries", 0)
        if retries > 0:
            return "under_pressure"

        # Novel territory: high topic novelty from cached drift data
        drift_cache = extras.get("_drift_cache", {})
        drift_data = drift_cache.get("drift_data", {})
        topic_novelty = drift_data.get("topic_novelty", 0.0)
        if topic_novelty >= 0.60:
            # Check user message for more specific shapes
            user_msg = ""
            if loop_data.user_message:
                user_msg = loop_data.user_message.output_text()

            if user_msg:
                if _CONVERGING_KEYWORDS.search(user_msg):
                    return "converging_constraints"
                if _IDENTITY_KEYWORDS.search(user_msg):
                    return "identity_pressure"

            return "novel_territory"

        # Check user message even without high novelty
        user_msg = ""
        if loop_data.user_message:
            user_msg = loop_data.user_message.output_text()

        if user_msg:
            if _CONVERGING_KEYWORDS.search(user_msg):
                return "converging_constraints"
            if _IDENTITY_KEYWORDS.search(user_msg):
                return "identity_pressure"

        return "steady_state"
