"""
Naive Surveillance Bridge --- integration wrapper for drift tracker.

Provides a module-level NaiveSurveillance instance that persists across
messages (module-level = process lifetime). Handles import failures
gracefully so the drift tracker degrades to pattern-only mode.

Three detection surfaces:
  1. Spike alerts (z-score deviation) — term + semantic matching
  2. Cumulative drift (rolling integral) — slow prestige creep
  3. Intent gate (content x action) — block prestige-publicizing deliverables

Usage from drift tracker:
    from _helpers.naive_bridge import get_surveillance, format_surveillance_injection
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)

# Add fusion_core to path for import
_workspace = os.environ.get("WORKSPACE_DIR", "/workspace/operationTorque")
_fc_src = os.path.join(_workspace, "fusion_core_repo", "src")
if _fc_src not in sys.path:
    sys.path.insert(0, _fc_src)

_surveillance = None
_init_attempted = False


def get_surveillance():
    """Return module-level NaiveSurveillance instance, or None if unavailable."""
    global _surveillance, _init_attempted
    if _init_attempted:
        return _surveillance

    _init_attempted = True
    try:
        from fusion_core.naive_surveillance import NaiveSurveillance

        shapes_path = os.environ.get(
            "ARCHETYPE_SHAPES_PATH",
            os.path.join(_workspace, "compliance-modules", "archetype_shapes.json"),
        )
        _surveillance = NaiveSurveillance(
            shapes_path=shapes_path,
            window_size=20,
            sigma_threshold=2.0,
            min_observations=3,
        )
        logger.info("Naive surveillance layer initialized (Bridge 2+3, semantic+drift)")
    except Exception as e:
        logger.warning(f"Naive surveillance unavailable: {e}")
        _surveillance = None

    return _surveillance


def format_surveillance_injection(surveillance_result, confirmed_families=None):
    """
    Format surveillance alerts + cumulative drifts into injection blocks.

    Returns str or None.
    """
    if not surveillance_result:
        return None

    has_alerts = bool(surveillance_result.alerts)
    has_drifts = bool(surveillance_result.cumulative_drifts)
    has_semantic = bool(surveillance_result.semantic_scores)

    if not has_alerts and not has_drifts:
        return None

    confirmed_families = confirmed_families or set()
    parts = []

    # Spike alerts block
    if has_alerts:
        lines = []
        for alert in surveillance_result.alerts[:5]:
            # Show both term matches and semantic matches
            sources = []
            if alert.matched_terms:
                sources.append("terms: " + ", ".join(alert.matched_terms[:3]))
            if alert.semantic_matches:
                sources.append("semantic: " + ", ".join(alert.semantic_matches[:2]))
            source_str = "; ".join(sources) if sources else "composite"

            confirm_tag = ""
            if alert.archetype in confirmed_families:
                confirm_tag = " [CONFIRMED]"
            lines.append(
                f"  - {alert.archetype}: z={alert.z_score:.1f}\u03c3 "
                f"({source_str}){confirm_tag}"
            )

        convergent = [a for a in surveillance_result.alerts if a.archetype in confirmed_families]

        parts.append(
            f"\n\n[NA\u00cfVE SURVEILLANCE \u2014 Abundance Monitor]\n"
            f"{len(surveillance_result.alerts)} archetype amplitudes deviate from baseline:\n"
            + "\n".join(lines)
        )

        if convergent:
            families = ", ".join(a.archetype for a in convergent)
            parts.append(
                f"\nConvergence: {families} confirmed by Harpoon "
                f"(ping-pong amplified)."
            )

    # Cumulative drift block — slow creep detection
    if has_drifts:
        drift_lines = []
        for d in surveillance_result.cumulative_drifts[:3]:
            trend_arrow = "\u2197" if d.trend > 0.01 else ("\u2198" if d.trend < -0.01 else "\u2192")
            drift_lines.append(
                f"  - {d.archetype}: integral={d.integral:.2f} "
                f"{trend_arrow} sustained={'yes' if d.sustained else 'no'}"
            )

        if not has_alerts:
            parts.append(f"\n\n[NA\u00cfVE SURVEILLANCE \u2014 Drift Monitor]")

        parts.append(
            f"\nCumulative drift (persistent patterns across messages):\n"
            + "\n".join(drift_lines)
            + "\nThese patterns don't spike in any single message but "
            + "accumulate over time \u2014 check if this is intentional."
        )

    parts.append(f"\n[/NA\u00cfVE SURVEILLANCE]")
    return "".join(parts)
