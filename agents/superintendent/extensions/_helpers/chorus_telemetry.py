"""
Chorus Telemetry — Structured JSONL event emission for the Ghost Chorus
and epitaph lifecycle. Observation only — no enforcement, no network calls.

Every event carries trust_tier: "detect" (observe only). Human annotations
in audit-logs/annotations/ can upgrade trust via the covenant model:
  detect → warning → critical

Fail-silent by contract: no function in this module ever raises.
"""

import os
import json
from datetime import datetime, timezone, timedelta

CHORUS_LOG_DIR = os.environ.get(
    "CHORUS_LOG_DIR",
    "/workspace/operationTorque/audit-logs/chorus",
)
ANNOTATION_DIR = os.environ.get(
    "ANNOTATION_DIR",
    "/workspace/operationTorque/audit-logs/annotations",
)

# Closed event type registry — mirrors harpoon module IDs
VALID_EVENT_TYPES = {
    "chorus_activation",
    "chorus_silence",
    "chorus_outcome",
    "epitaph_created",
    "epitaph_boosted",
    "epitaph_decayed",
    "epitaph_retrieved",
    "volume_snapshot",
}

VALID_ANNOTATION_ACTIONS = {
    "trust_up",
    "trust_down",
    "gate",
    "open",
    "note",
    "archive",
}


def log_chorus_event(event_type: str, payload: dict) -> None:
    """Write one JSONL line to audit-logs/chorus/YYYY-MM-DD.jsonl."""
    try:
        now = datetime.now(timezone.utc)
        entry = {
            "timestamp": now.isoformat(),
            "event_type": event_type,
            "trust_tier": "detect",
        }
        entry.update(payload)
        os.makedirs(CHORUS_LOG_DIR, exist_ok=True)
        log_path = os.path.join(CHORUS_LOG_DIR, f"{now.strftime('%Y-%m-%d')}.jsonl")
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # fail-silent — never crash caller


def log_annotation(
    target_type: str,
    target_id: str,
    action: str,
    reason: str,
    operator: str,
) -> dict | None:
    """Write one annotation JSONL line to audit-logs/annotations/YYYY-MM-DD.jsonl."""
    try:
        now = datetime.now(timezone.utc)
        entry = {
            "timestamp": now.isoformat(),
            "operator": operator,
            "target_type": target_type,
            "target_id": target_id,
            "action": action,
            "reason": reason,
        }
        os.makedirs(ANNOTATION_DIR, exist_ok=True)
        log_path = os.path.join(ANNOTATION_DIR, f"{now.strftime('%Y-%m-%d')}.jsonl")
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        return entry
    except Exception:
        return None


def read_annotations(target_id: str | None = None, since_days: int = 7) -> list[dict]:
    """Read annotation JSONLs for the last N days, optionally filtered by target_id."""
    results = []
    try:
        now = datetime.now(timezone.utc)
        for day_offset in range(since_days):
            date = now - timedelta(days=day_offset)
            log_path = os.path.join(
                ANNOTATION_DIR, f"{date.strftime('%Y-%m-%d')}.jsonl"
            )
            if not os.path.isfile(log_path):
                continue
            with open(log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if target_id and entry.get("target_id") != target_id:
                        continue
                    results.append(entry)
    except Exception:
        pass
    return results
