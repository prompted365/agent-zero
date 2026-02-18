"""
Economy Whisper — Ambient UCoin Economy Context from Nautilus Swarm

Fires at message_loop_prompts_after (_52, AFTER Idea Whisper _50,
BEFORE Drift Tracker _55). Injects 1-line macro economy context
when conversation touches economy/supply/reserve/rate/mint topics.

Design principle: Same as Idea Whisper. Context landscaping, not
instructions. One-line macro injection that disappears into ambient
awareness. If Mogul says "the economy whisper reports" — it has failed.

v1.1: Governance tags (HALT, RESERVE_BREACH, FROZEN, STALENESS_LAG,
RATE_BAND_BREACH) appended as macro-only suffixes. Tags, not instructions.
Fail-silent degradation to v1.0 format if v1.1 keys absent.

Fail-silent: If the foreman is unreachable, no injection occurs.
"""

import os
import re
import aiohttp
from python.helpers.extension import Extension
from agent import LoopData

# Relevance gate: economy/supply/reserve/rate/mint keywords
_RELEVANCE_KEYWORDS = re.compile(
    r"(econom|supply|reserve|mint|burn|rate|ucoin|inflation|deflation"
    r"|liquidity|monetary|circuit.?break|frozen|phase|treasury"
    r"|halt|breach|stale)",
    re.IGNORECASE,
)

# Configuration via environment
FOREMAN_URL = os.environ.get("NAUTILUS_FOREMAN_URL", "http://localhost:8090")


class EconomyWhisper(Extension):
    __version__ = "1.1.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "LoopData.extras_persistent[economy_context, _economy_last_gen] (write)"

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # Relevance gate
        if not self._is_relevant(loop_data):
            loop_data.extras_persistent.pop("economy_context", None)
            return

        # Fetch economy snapshot from foreman (fail-silent)
        try:
            economy = await self._fetch_economy()
        except Exception:
            return

        if not economy:
            return

        econ_data = economy.get("economy")
        if not econ_data:
            return

        # Cooldown: skip if snapshot generation unchanged
        snap_gen = econ_data.get("generation", 0)
        last_gen = loop_data.extras_persistent.get("_economy_last_gen", 0)
        if snap_gen == last_gen and snap_gen > 0:
            return

        # Build 1-line macro context
        supply = econ_data.get("supply", 0.0)
        rate = econ_data.get("rate", 0.0)
        reserve_ratio = econ_data.get("reserve_ratio", 0.0)
        phase = econ_data.get("phase", "SimOnly")
        rate_delta = econ_data.get("rate_delta", 0.0)
        growth = econ_data.get("supply_growth_rate", 0.0)

        delta_dir = "+" if rate_delta >= 0 else ""
        growth_dir = "+" if growth >= 0 else ""

        whisper = (
            f"[ECONOMY: supply={supply:.0f} rate={rate:.4f}({delta_dir}{rate_delta:.4f}) "
            f"reserves={reserve_ratio:.1%} growth={growth_dir}{growth:.4%} phase={phase}"
        )

        # v1.1 governance tags (fail-silent degradation)
        tags = self._compute_tags(economy, econ_data)
        if tags:
            whisper += " " + " ".join(tags)

        whisper += "]"

        loop_data.extras_persistent["economy_context"] = whisper
        loop_data.extras_persistent["_economy_last_gen"] = snap_gen

        self.agent.context.log.log(
            type="util",
            heading=f"Economy Whisper: gen={snap_gen} phase={phase} R/S={reserve_ratio:.3f}",
        )

    def _compute_tags(self, response, econ_data):
        """Compute governance tags from v1.1 response fields. Returns list of tag strings."""
        tags = []
        try:
            # mint_halted from economy snapshot
            if econ_data.get("mint_halted"):
                tags.append("#HALT")

            # breach_flags from v1.1 response envelope
            breach = response.get("breach_flags", {})
            if breach.get("reserve_breach"):
                tags.append("#RESERVE_BREACH")
            if breach.get("frozen"):
                tags.append("#FROZEN")
            if breach.get("rate_band_breach"):
                tags.append("#RATE_BAND_BREACH")

            # staleness from v1.1 response envelope
            staleness = response.get("staleness", {})
            if staleness.get("stale"):
                tags.append("#STALENESS_LAG")
        except Exception:
            # Fail-silent: degrade to v1.0 (no tags)
            pass

        return tags

    def _is_relevant(self, loop_data: LoopData) -> bool:
        """Check if conversation touches economy topics."""
        if loop_data.user_message:
            user_text = loop_data.user_message.output_text()
            if user_text and _RELEVANCE_KEYWORDS.search(user_text):
                return True

        # Maintain continuity if previously injected
        if loop_data.extras_persistent.get("economy_context"):
            return True

        return False

    async def _fetch_economy(self):
        """Fetch economy snapshot from foreman. Returns dict or raises."""
        timeout = aiohttp.ClientTimeout(total=2.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{FOREMAN_URL}/foreman/economy") as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
