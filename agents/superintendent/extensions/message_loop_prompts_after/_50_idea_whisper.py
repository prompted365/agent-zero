"""
Idea Whisper — Ambient Opportunity Context from Nautilus Swarm

Fires at message_loop_prompts_after (_50, AFTER Ghost Chorus _45,
BEFORE Drift Tracker _55). Injects swarm opportunity landscape as
ambient context — not directives.

Design principle: Same as Ghost Chorus. Context landscaping, not
instructions. The whisper is correct when Mogul identifies opportunities
more acutely without attribution. If Mogul's response references
"the swarm suggests" or "according to the barometer" — the whisper
has failed.

Fail-silent: If the foreman is unreachable, no injection occurs.
No error, no log spam. The swarm is simply not running.
"""

import os
import re
import aiohttp
from python.helpers.extension import Extension
from agent import LoopData

# Relevance gate: only inject when conversation touches these domains
_RELEVANCE_KEYWORDS = re.compile(
    r"(trad(?:e|ing)|trust|swarm|mint|barometer|market|position"
    r"|drawdown|signal|opportunity|risk|hedge|alpha|confidence"
    r"|portfolio|asset|equity|ucoin|nautilus|live|paper.?trad)",
    re.IGNORECASE,
)

# Configuration via environment
FOREMAN_URL = os.environ.get("NAUTILUS_FOREMAN_URL", "http://nautilus-foreman:8090")
MIN_IDEAS = int(os.environ.get("IDEA_WHISPER_MIN_IDEAS", "1"))
MAX_AGE_GENERATIONS = int(os.environ.get("IDEA_WHISPER_MAX_AGE", "50"))
# Cooldown: minimum cycles between re-injecting the same idea IDs
COOLDOWN_CYCLES = int(os.environ.get("IDEA_WHISPER_COOLDOWN", "10"))


class IdeaWhisper(Extension):
    __version__ = "1.1.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "LoopData.extras_persistent[swarm_ideas, _whisper_last_ids, _whisper_last_gen] (write)"

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # Relevance gate: skip if conversation doesn't touch trading/trust/swarm
        if not self._is_relevant(loop_data):
            loop_data.extras_persistent.pop("swarm_ideas", None)
            return

        # Fetch barometer + ideas from foreman (fail-silent)
        try:
            barometer, ideas = await self._fetch_swarm_state()
        except Exception:
            return

        if not ideas or not barometer:
            return

        # Fix 0.4: Use last_cycle_generation from foreman, not generations_in_phase
        last_cycle_gen = ideas.get("last_cycle_generation", 0)
        idea_data = ideas.get("ideas")
        if not idea_data:
            return

        # Filter stale ideas by TTL using last_cycle_generation
        all_tiers = []
        for tier_key in ("opportunities", "suggestions", "signals"):
            tier_ideas = idea_data.get(tier_key, [])
            fresh = []
            for idea in tier_ideas:
                tc = idea.get("trust_companion", {})
                idea_gen = tc.get("generation", 0)
                age = last_cycle_gen - idea_gen
                if age <= MAX_AGE_GENERATIONS:
                    fresh.append(idea)
            all_tiers.append((tier_key, fresh))

        total_fresh = sum(len(t[1]) for t in all_tiers)
        if total_fresh < MIN_IDEAS:
            return

        # Cooldown: track last injected idea IDs to avoid re-injection spam
        current_ids = set()
        for _, tier_ideas in all_tiers:
            for idea in tier_ideas:
                current_ids.add(idea.get("id", ""))

        last_ids = set(loop_data.extras_persistent.get("_whisper_last_ids", []))
        last_gen = loop_data.extras_persistent.get("_whisper_last_gen", 0)

        # If same idea set AND within cooldown window, skip injection
        if current_ids == last_ids and (last_cycle_gen - last_gen) < COOLDOWN_CYCLES:
            return

        # Build ambient context block
        sections = []

        # Barometer header
        phase = barometer.get("phase", "SimOnly")
        score = barometer.get("barometer_score", 0.0)
        trend_val = barometer.get("trend", 0.0)
        trend_dir = "rising" if trend_val > 0.001 else ("falling" if trend_val < -0.001 else "stable")
        sections.append(
            f"[TRANSITION BAROMETER: {phase} (score={score:.3f}, trend={trend_dir})]"
        )

        # Opportunities — high confidence
        opportunities = dict(all_tiers).get("opportunities", [])
        if opportunities:
            lines = ["[SWARM LANDSCAPE -- HIGH CONFIDENCE]"]
            for opp in opportunities:
                lines.append(f"  - {opp['title']}: {opp['detail']}")
            sections.append("\n".join(lines))

        # Suggestions — emerging
        suggestions = dict(all_tiers).get("suggestions", [])
        if suggestions:
            lines = ["[SWARM LANDSCAPE -- EMERGING]"]
            for sug in suggestions:
                lines.append(f"  - {sug['title']}")
            sections.append("\n".join(lines))

        # Signals — ambient
        signals = dict(all_tiers).get("signals", [])
        if signals:
            lines = ["[SWARM LANDSCAPE -- AMBIENT]"]
            for sig in signals:
                lines.append(f"  - {sig['title']}")
            sections.append("\n".join(lines))

        if len(sections) <= 1:
            # Only barometer header, no actual ideas
            return

        whisper = "\n\n".join(sections)
        loop_data.extras_persistent["swarm_ideas"] = whisper
        loop_data.extras_persistent["_whisper_last_ids"] = list(current_ids)
        loop_data.extras_persistent["_whisper_last_gen"] = last_cycle_gen

        self.agent.context.log.log(
            type="util",
            heading=f"Idea Whisper: {total_fresh} ideas ({len(opportunities)} opportunities, {len(suggestions)} suggestions, {len(signals)} signals)",
        )

    def _is_relevant(self, loop_data: LoopData) -> bool:
        """Check if the current conversation touches trading/trust/swarm topics."""
        # Check user message
        if loop_data.user_message:
            user_text = loop_data.user_message.output_text()
            if user_text and _RELEVANCE_KEYWORDS.search(user_text):
                return True

        # Check if swarm_ideas were previously injected (maintain continuity)
        if loop_data.extras_persistent.get("swarm_ideas"):
            return True

        return False

    async def _fetch_swarm_state(self):
        """Fetch barometer and ideas from foreman. Returns (barometer, ideas) or raises."""
        timeout = aiohttp.ClientTimeout(total=2.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{FOREMAN_URL}/foreman/barometer") as resp:
                if resp.status != 200:
                    return None, None
                barometer = await resp.json()

            async with session.get(f"{FOREMAN_URL}/foreman/ideas") as resp:
                if resp.status != 200:
                    return barometer, None
                ideas = await resp.json()

        return barometer, ideas
