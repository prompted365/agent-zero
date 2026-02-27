"""
Fork Accounting — Monologue-End Fork Event Counter + Economy Bridge

Fires at monologue_end AFTER epitaph extraction (_65). Counts fork events
(ecotone retries, corrective feedback pops, motivation blocks) that occurred
during this monologue and reports them to the Nautilus Foreman economy.

Fork events are the economy's signal that governance is actively intervening.
Each fork has a cost (fork_burn channel in burn.rs). This extension bridges
the governance layer to the economic layer.

Design:
- Reads from AgentContext.data (cross-message persistence) for ecotone retries,
  motivation flags, and lock events that occurred this monologue.
- Posts fork count to Foreman /foreman/fork_events endpoint (fire-and-forget).
- Falls back to writing a JSONL entry for offline consumption by economy-tick.py.
- Fail-silent: never crashes the extension chain.
"""

import os
import sys
import json
import aiohttp
from datetime import datetime, timezone
from python.helpers.extension import Extension
from agent import LoopData
from python.helpers.print_style import PrintStyle

# Add extensions dir to path for _helpers import
_ext_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)

FOREMAN_URL = os.environ.get("NAUTILUS_FOREMAN_URL", "http://nautilus-foreman:8090")
FORK_LOG_DIR = os.environ.get(
    "FORK_LOG_DIR",
    "/workspace/operationTorque/audit-logs/economy",
)


class ForkAccounting(Extension):
    __version__ = "1.0.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "AgentContext.data[_fork_events_total, _fork_events_last_monologue]"

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        try:
            fork_count = self._count_fork_events()

            if fork_count == 0:
                return

            # Update cumulative counter
            total = (self.agent.context.get_data("_fork_events_total") or 0) + fork_count
            self.agent.context.set_data("_fork_events_total", total)
            self.agent.context.set_data("_fork_events_last_monologue", fork_count)

            # Report to foreman (fire-and-forget)
            reported = await self._report_to_foreman(fork_count)

            # Always log to JSONL as backup
            self._log_fork_events(fork_count, total, reported)

            PrintStyle.hint(
                f"[ForkAccounting] {fork_count} fork event(s) this monologue "
                f"(total: {total}, reported: {reported})"
            )

        except Exception as e:
            PrintStyle.error(f"[ForkAccounting] Error: {e}")

    def _count_fork_events(self) -> int:
        """Count fork-like events from this monologue's governance activity."""
        count = 0

        # 1. Ecotone retries (each retry = response popped + feedback injected = fork)
        retries = self.agent.context.get_data("ecotone_retries") or 0
        count += retries

        # 2. Motivation gate blocks (prestige pursuit blocked = corrective fork)
        motivation_flag = self.agent.context.get_data("motivation_flag")
        if motivation_flag and motivation_flag.get("blocked"):
            count += 1

        # 3. LOCK events (human review checkpoint = containment fork)
        lock_handled = self.agent.context.get_data("_lock_handled_this_monologue")
        if lock_handled:
            count += 1

        # 4. Ecotone failures stored in cross-message persistence
        ecotone_failures = self.agent.context.get_data("_ecotone_failures") or []
        # Only count failures not already counted via retries
        # (retries are retry attempts; failures list may have the final failure too)
        extra_failures = max(0, len(ecotone_failures) - retries)
        count += extra_failures

        return count

    async def _report_to_foreman(self, fork_count: int) -> bool:
        """POST fork events to Nautilus Foreman. Returns True if successful."""
        try:
            url = f"{FOREMAN_URL}/foreman/fork_events"
            payload = {
                "fork_events": fork_count,
                "source": "mogul_extension",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    def _log_fork_events(self, count: int, total: int, reported: bool):
        """Append fork event record to JSONL for offline economy-tick consumption."""
        try:
            os.makedirs(FORK_LOG_DIR, exist_ok=True)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log_path = os.path.join(FORK_LOG_DIR, f"fork_events_{today}.jsonl")
            entry = {
                "type": "fork_event",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "count": count,
                "cumulative_total": total,
                "reported_to_foreman": reported,
                "source": "monologue_end/_70_fork_accounting",
            }
            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
