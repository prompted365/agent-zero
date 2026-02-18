"""
Foreman Economy — Read-only query tool for the Nautilus Swarm economy.

Actions: snapshot, barometer, health, ideas
All operations are non-mutating reads from lock-free ArcSwap snapshots.
"""

import os
import json
import aiohttp
from python.helpers.tool import Tool, Response

FOREMAN_URL = os.environ.get("NAUTILUS_FOREMAN_URL", "http://nautilus-foreman:8090")


class ForemanEconomy(Tool):
    """Read-only query tool for the Nautilus Swarm economy Foreman."""

    async def execute(self, action="snapshot", **kwargs):
        try:
            if action == "snapshot":
                return await self._action_snapshot()
            elif action == "barometer":
                return await self._action_barometer()
            elif action == "health":
                return await self._action_health()
            elif action == "ideas":
                return await self._action_ideas()
            else:
                return Response(
                    message=f"Unknown action: {action}. Available: snapshot, barometer, health, ideas",
                    break_loop=False,
                )
        except aiohttp.ClientError as e:
            return Response(
                message=f"Foreman unreachable at {FOREMAN_URL}: {e}",
                break_loop=False,
            )
        except Exception as e:
            return Response(
                message=f"Foreman economy error: {e}",
                break_loop=False,
            )

    async def _action_snapshot(self):
        """Full economy snapshot with thresholds, breach flags, staleness."""
        data = await self._get("/foreman/economy")
        econ = data.get("economy", {})
        breach = data.get("breach_flags", {})
        staleness = data.get("staleness", {})
        thresholds = data.get("thresholds", {})

        lines = ["## Economy Snapshot"]
        if econ:
            lines.append(f"- Generation: {econ.get('generation', '?')}")
            lines.append(f"- Supply: {econ.get('supply', 0):.2f}")
            lines.append(f"- Reserves: {econ.get('reserves', 0):.2f}")
            lines.append(f"- Reserve Ratio: {econ.get('reserve_ratio', 0):.4f}")
            lines.append(f"- Rate: {econ.get('rate', 0):.6f} (delta: {econ.get('rate_delta', 0):+.6f})")
            lines.append(f"- Phase: {econ.get('phase', '?')}")
            lines.append(f"- Mint Total: {econ.get('mint_total', 0):.2f}")
            lines.append(f"- Burn Total: {econ.get('burn_total', 0):.2f}")
            lines.append(f"- Growth Rate: {econ.get('supply_growth_rate', 0):.6f}")
            lines.append(f"- Mint Halted: {econ.get('mint_halted', False)}")
            if econ.get("mint_halt_reason"):
                lines.append(f"- Halt Reason: {econ['mint_halt_reason']}")
            bb = econ.get("burn_breakdown")
            if bb:
                lines.append(f"- Burn Breakdown: gap={bb.get('gap_burn',0):.2f} regression={bb.get('regression_burn',0):.2f} fee={bb.get('fee_burn',0):.2f} demurrage={bb.get('demurrage_burn',0):.2f}")
        else:
            lines.append("- No economy snapshot available (Foreman may not have cycled yet)")

        lines.append("\n## Breach Flags")
        for k, v in breach.items():
            lines.append(f"- {k}: {v}")

        lines.append("\n## Staleness")
        lines.append(f"- Stale: {staleness.get('stale', False)}")
        lines.append(f"- Lag: {staleness.get('lag_generations', 0)} generations")

        lines.append("\n## Thresholds (Current Phase)")
        for k, v in thresholds.items():
            lines.append(f"- {k}: {v}")

        lines.append(f"\n## Meta")
        lines.append(f"- Schema: {data.get('schema_version', '?')}")
        lines.append(f"- Params Hash: {data.get('params_hash', '?')}")

        return Response(message="\n".join(lines), break_loop=False)

    async def _action_barometer(self):
        """Phase barometer: phase, score, trend, frozen, dwell."""
        data = await self._get("/foreman/barometer")
        lines = ["## Barometer"]
        lines.append(f"- Phase: {data.get('phase', '?')}")
        lines.append(f"- Score: {data.get('barometer_score', 0):.4f}")
        lines.append(f"- Trend: {data.get('trend', 0):+.4f}")
        lines.append(f"- Frozen: {data.get('frozen', False)}")
        lines.append(f"- Generations in Phase: {data.get('generations_in_phase', 0)}")
        lines.append(f"- Last Cycle Gen: {data.get('last_cycle_generation', 0)}")
        return Response(message="\n".join(lines), break_loop=False)

    async def _action_health(self):
        """Quick health check: is Foreman reachable?"""
        timeout = aiohttp.ClientTimeout(total=3.0)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{FOREMAN_URL}/health") as resp:
                    body = await resp.text()
                    return Response(
                        message=f"Foreman healthy: {resp.status} — {body}",
                        break_loop=False,
                    )
        except Exception as e:
            return Response(
                message=f"Foreman UNHEALTHY at {FOREMAN_URL}: {e}",
                break_loop=False,
            )

    async def _action_ideas(self):
        """Prospector ideas: opportunities, suggestions, signals."""
        data = await self._get("/foreman/ideas")
        lines = ["## Prospector Ideas"]
        ideas = data.get("ideas", {})
        has_ideas = False
        for tier in ("opportunities", "suggestions", "signals"):
            tier_ideas = ideas.get(tier, [])
            if tier_ideas:
                has_ideas = True
                lines.append(f"\n### {tier.title()}")
                for idea in tier_ideas:
                    title = idea.get("title", "?")
                    detail = idea.get("detail", "")
                    if detail:
                        lines.append(f"- {title}: {detail}")
                    else:
                        lines.append(f"- {title}")
        if not has_ideas:
            lines.append("No active ideas.")
        lines.append(f"\nLast Cycle Generation: {data.get('last_cycle_generation', '?')}")
        return Response(message="\n".join(lines), break_loop=False)

    async def _get(self, path):
        """Async HTTP GET helper. Returns parsed JSON."""
        timeout = aiohttp.ClientTimeout(total=5.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{FOREMAN_URL}{path}") as resp:
                return await resp.json()
