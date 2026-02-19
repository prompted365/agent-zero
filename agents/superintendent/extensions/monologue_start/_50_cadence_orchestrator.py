"""
Cadence Orchestrator — Time-Based Trigger System

Fires at monologue_start. Checks whether scheduled maintenance actions
are due and injects directives into the prompt context for Mogul to
dispatch via call_subordinate.

Key design: Extension injects directives, it does NOT execute actions
directly. Mogul reads the directive, delegates to subordinates, and
the confidence gates verify output. Trust but verify.

State persistence: Cross-session state on bind mount at
/workspace/operationTorque/cadence-state/mogul_cadence.json
Within-session state in extras_persistent.
"""

import os
import json
import logging
import time
from datetime import datetime, timezone
from python.helpers.extension import Extension
from agent import LoopData
from python.helpers.log import LogItem

CADENCE_STATE_DIR = os.environ.get(
    "CADENCE_STATE_DIR",
    "/workspace/operationTorque/cadence-state",
)
CADENCE_STATE_FILE = os.path.join(CADENCE_STATE_DIR, "mogul_cadence.json")

logger = logging.getLogger(__name__)

# Trigger definitions: name, interval_minutes, directive template
TRIGGERS = [
    {
        "name": "health_check",
        "interval_minutes": int(os.environ.get("CADENCE_HEALTH_INTERVAL", "60")),
        "directive": (
            "Run an estate health check. Verify all services are operational:\n"
            "  - RuVector (port 6334)\n"
            "  - Crawlset (port 8001)\n"
            "  - Redis (port 6379)\n"
            "  - Docker containers\n"
            "Delegate to a subordinate with FOUNDATIONAL_RIGOR profile.\n"
            "Report anomalies only — silence means health."
        ),
    },
    {
        "name": "memory_consolidation",
        "interval_minutes": int(os.environ.get("CADENCE_MEMORY_INTERVAL", "240")),
        "directive": (
            "Trigger memory consolidation:\n"
            "  1. Use ruvector_query to check collection stats for mogul_memory\n"
            "  2. If > 50 new documents since last consolidation, trigger GNN training\n"
            "  3. Review graph structure for orphaned entity nodes\n"
            "Delegate to a subordinate."
        ),
    },
    {
        "name": "compliance_scan",
        "interval_minutes": int(os.environ.get("CADENCE_COMPLIANCE_INTERVAL", "480")),
        "directive": (
            "Run pattern anchor scan on today's operational output:\n"
            "  1. Use boris_strike session_scan on today's ecotone logs\n"
            "  2. Review arc summary for STAGNATING patterns\n"
            "  3. If stagnation detected, propose adjustments\n"
            "Delegate to a subordinate."
        ),
    },
    {
        "name": "intelligence_check",
        "interval_minutes": int(os.environ.get("CADENCE_INTEL_INTERVAL", "360")),
        "directive": (
            "Check web intelligence status:\n"
            "  1. Use crawlset_extract monitors_list to see active monitors\n"
            "  2. Use crawlset_extract analytics_dashboard for summary stats\n"
            "  3. Note any monitors that haven't run recently\n"
            "Delegate to a subordinate."
        ),
    },
]


class CadenceOrchestrator(Extension):
    __version__ = "1.0.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "LoopData.extras_persistent[cadence_state]"

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # Only fire on first iteration of a monologue
        if loop_data.iteration != 0:
            return

        log_item = self.agent.context.log.log(
            type="util",
            heading="Cadence orchestrator: checking triggers...",
        )

        try:
            state = self._load_state()
            now = time.time()
            due_triggers = []

            for trigger in TRIGGERS:
                name = trigger["name"]
                last_run = state.get(name, {}).get("last_run", 0)
                interval_sec = trigger["interval_minutes"] * 60

                if now - last_run >= interval_sec:
                    due_triggers.append(trigger)
                    state[name] = {
                        "last_run": now,
                        "last_run_iso": datetime.now(timezone.utc).isoformat(),
                    }

            if not due_triggers:
                log_item.update(heading="Cadence orchestrator: no triggers due.")
                return

            # Save updated state
            self._save_state(state)

            # Also save to extras_persistent for within-session access
            loop_data.extras_persistent["cadence_state"] = state

            # Build injection directive
            directives = []
            for trigger in due_triggers:
                directives.append(
                    f"### {trigger['name'].replace('_', ' ').title()} (every {trigger['interval_minutes']}min)\n"
                    f"{trigger['directive']}"
                )

            injection = (
                "\n\n[CADENCE — Scheduled Actions]\n"
                f"The following {len(due_triggers)} scheduled action(s) are due. "
                f"Dispatch each via call_subordinate after handling the user's current request.\n\n"
                + "\n\n".join(directives)
                + "\n[/CADENCE]\n"
            )

            loop_data.extras_persistent["cadence_directives"] = injection

            log_item.update(
                heading=f"Cadence orchestrator: {len(due_triggers)} trigger(s) due — {', '.join(t['name'] for t in due_triggers)}",
            )

        except Exception as e:
            log_item.update(
                heading=f"Cadence orchestrator: error — {str(e)[:200]}",
            )

    def _load_state(self) -> dict:
        """Load cadence state from persistent file."""
        if os.path.isfile(CADENCE_STATE_FILE):
            try:
                with open(CADENCE_STATE_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                corrupt_name = CADENCE_STATE_FILE + f".corrupt.{int(time.time())}"
                try:
                    os.rename(CADENCE_STATE_FILE, corrupt_name)
                except OSError:
                    pass
                logger.warning(f"Cadence state corrupted, reset. Saved to {corrupt_name}: {e}")
        return {}

    def _save_state(self, state: dict):
        """Save cadence state to persistent file."""
        os.makedirs(CADENCE_STATE_DIR, exist_ok=True)
        tmp = CADENCE_STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, CADENCE_STATE_FILE)
