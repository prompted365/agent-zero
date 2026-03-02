"""
Governance Witness Record Writer — boundary audit events for Lane C decisions.

Appends typed JSONL records to audit-logs/governance/YYYY-MM-DD.jsonl.
Same fail-silent pattern as signal_emitter.py and chorus_telemetry.py —
witness logging must never crash the host extension.

Schema (boundary_witness@1):
  {
    "type": "witness",
    "version": 1,
    "timestamp": "ISO-8601",
    "decision": "route_lane_c" | "escalate_lock" | "coherence_pass" | "coherence_fail",
    "trigger_councils": [{"council_id": str, "number": int, "clusters": [str], "amplitude": float}],
    "incompatibility_scores": [{"pair": [int, int], "score": float, "interpretation": str}],
    "cross_cluster": bool,
    "trace_id": str,
    "outcome": str,
    "metadata": {}
  }

Usage:
    from _helpers.governance_witness import record_witness
    record_witness(
        decision="coherence_fail",
        trigger_councils=[...],
        incompatibility_scores=[...],
        trace_id="abc123",
        outcome="LOCK candidate emitted",
    )
"""

import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_workspace = os.environ.get("WORKSPACE_DIR", "/workspace/operationTorque")
_GOVERNANCE_LOG_DIR = os.path.join(_workspace, "audit-logs", "governance")


def _ensure_dir():
    """Create governance log directory if it doesn't exist."""
    try:
        os.makedirs(_GOVERNANCE_LOG_DIR, exist_ok=True)
    except Exception:
        pass


def _log_path() -> str:
    """Today's governance witness JSONL path."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(_GOVERNANCE_LOG_DIR, f"{today}.jsonl")


def record_witness(
    decision: str,
    trigger_councils: list[dict],
    incompatibility_scores: Optional[list[dict]] = None,
    cross_cluster: bool = False,
    trace_id: str = "",
    outcome: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> bool:
    """
    Append a governance witness record to today's JSONL.

    Args:
        decision: One of "route_lane_c", "escalate_lock", "coherence_pass", "coherence_fail".
        trigger_councils: List of activated council dicts with council_id, number, clusters, amplitude.
        incompatibility_scores: Optional pairwise scores for the trigger councils.
        cross_cluster: Whether the trigger councils span different tension clusters.
        trace_id: Per-monologue trace ID for correlation.
        outcome: Human-readable outcome description.
        metadata: Additional context.

    Returns True on success, False on failure (fail-silent).
    """
    try:
        _ensure_dir()
        record = {
            "type": "witness",
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "trigger_councils": trigger_councils,
            "incompatibility_scores": incompatibility_scores or [],
            "cross_cluster": cross_cluster,
            "trace_id": trace_id,
            "outcome": outcome,
            "metadata": metadata or {},
        }
        line = json.dumps(record, separators=(",", ":")) + "\n"
        with open(_log_path(), "a") as f:
            f.write(line)
        return True
    except Exception as e:
        logger.warning(f"governance_witness write failed: {e}")
        return False


def read_witnesses(
    date: Optional[str] = None,
    decision_filter: Optional[str] = None,
) -> list[dict]:
    """
    Read witness records from a date's JSONL.

    Args:
        date: YYYY-MM-DD string. Defaults to today.
        decision_filter: If set, only return records with this decision type.

    Returns list of parsed witness records.
    """
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(_GOVERNANCE_LOG_DIR, f"{date}.jsonl")

    if not os.path.exists(path):
        return []

    records = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if decision_filter and rec.get("decision") != decision_filter:
                    continue
                records.append(rec)
    except Exception as e:
        logger.warning(f"governance_witness read failed: {e}")

    return records
