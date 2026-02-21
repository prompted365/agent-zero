"""
Signal Emitter — Outbound Siren Signal Writer for Mogul Extensions

Writes CGG v3 Siren signal entries to the shared bind-mount JSONL store
at /workspace/operationTorque/audit-logs/signals/YYYY-MM-DD.jsonl.

This is the bridge that resolves the "no outbound push pathway" gap:
Mogul extensions can now emit structured signals that Homeskillet's
/siren tick engine reads on the next cycle.

Contract:
- Fail-silent: no function ever raises.
- Append-only: never modify old JSONL lines.
- Latest-entry-per-ID-wins semantics.
- PRESTIGE band is governance-blocked (silently dropped).
"""

import os
import json
import hashlib
from datetime import datetime, timezone

SIGNAL_LOG_DIR = os.environ.get(
    "SIGNAL_LOG_DIR",
    "/workspace/operationTorque/audit-logs/signals",
)

# Band attenuation (dB equiv for effective_volume computation)
BAND_ATTENUATION = {
    "PRIMITIVE": 0,
    "COGNITIVE": -6,
    "SOCIAL": -12,
    "PRESTIGE": None,  # governance-blocked
}

VALID_KINDS = {"BEACON", "LESSON", "OPPORTUNITY", "TENSION"}
VALID_BANDS = {"PRIMITIVE", "COGNITIVE", "SOCIAL"}
VALID_STATUSES = {"active", "acknowledged", "working", "resolved", "expired", "warranted"}


def emit_signal(
    signal_id,
    kind,
    band,
    subsystem,
    source,
    signature,
    volume=30,
    volume_rate=10,
    max_volume=100,
    ttl_hours=24,
    suggested_checks=None,
    links=None,
    summary="",
):
    """Emit a new Siren signal to the JSONL store.

    Args:
        signal_id: Unique ID (e.g. "sig_2026-02-20T03:00Z_ecotone_smoothing_abc1")
        kind: BEACON | LESSON | OPPORTUNITY | TENSION
        band: PRIMITIVE | COGNITIVE | SOCIAL (PRESTIGE is silently dropped)
        subsystem: e.g. "ecotone", "nautilus_swarm", "ruvector"
        source: file:line reference
        signature: short descriptive string for payload
        volume: initial volume (default 30)
        volume_rate: volume increase per tick (default 10)
        max_volume: volume cap (default 100)
        ttl_hours: time-to-live in hours (default 24)
        suggested_checks: list of check strings
        links: list of file path strings
        summary: longer description for payload
    """
    try:
        if band == "PRESTIGE" or band not in VALID_BANDS:
            return
        if kind not in VALID_KINDS:
            return

        now = datetime.now(timezone.utc)
        entry = {
            "type": "signal",
            "id": signal_id,
            "kind": kind,
            "band": band,
            "motivation_layer": band,
            "source": source,
            "source_date": now.strftime("%Y-%m-%d"),
            "subsystem": subsystem,
            "volume": volume,
            "volume_rate": volume_rate,
            "max_volume": max_volume,
            "ttl_hours": ttl_hours,
            "hearing_targets": [
                {"actor": "homeskillet", "threshold": 40},
                {"actor": "mogul", "threshold": 50},
            ],
            "escalation": {
                "warrant_threshold": 80,
                "warrant_id": "",
            },
            "payload": {
                "signature": signature,
                "summary": summary,
                "suggested_checks": suggested_checks or [],
                "links": links or [],
            },
            "status": "active",
            "last_tick_at": "",
            "tick_count": 0,
            "created_at": now.isoformat(),
        }

        _append_signal(entry)
    except Exception:
        pass


def update_signal_status(signal_id, new_status, note=""):
    """Update an existing signal's status by appending a new entry.

    Use status="working" to lock a signal (freeze volume accrual).
    Use status="resolved" when the root cause is fixed.
    """
    try:
        if new_status not in VALID_STATUSES:
            return

        now = datetime.now(timezone.utc)
        # Read the latest state for this signal
        latest = _read_latest_signal(signal_id)
        if not latest:
            return

        latest["status"] = new_status
        latest["last_tick_at"] = now.isoformat()

        if new_status == "working":
            latest["working_since"] = now.isoformat()
        elif new_status == "resolved":
            latest["resolved_at"] = now.isoformat()
            latest["resolution_note"] = note

        _append_signal(latest)
    except Exception:
        pass


def make_signal_id(subsystem, event_tag):
    """Generate a deterministic signal ID from subsystem + event tag.

    Returns: "sig_YYYY-MM-DDTHH:MMZ_<subsystem>_<event_tag>"
    """
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H:%MZ")
    return f"sig_{ts}_{subsystem}_{event_tag}"


def make_dedup_signal_id(subsystem, dedup_key):
    """Generate a signal ID that deduplicates on a stable key.

    Uses today's date + subsystem + hash of dedup_key.
    Same dedup_key on the same day produces the same ID,
    preventing duplicate signals from repeated extension firings.

    Returns: "sig_YYYY-MM-DDT00:00Z_<subsystem>_<4char_hash>"
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    h = hashlib.sha256(f"{today}:{subsystem}:{dedup_key}".encode()).hexdigest()[:4]
    return f"sig_{today}T00:00Z_{subsystem}_{h}"


def _append_signal(entry):
    """Append a signal entry to today's JSONL file."""
    try:
        os.makedirs(SIGNAL_LOG_DIR, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = os.path.join(SIGNAL_LOG_DIR, f"{today}.jsonl")
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _read_latest_signal(signal_id):
    """Read the latest state of a signal from the JSONL store.

    Scans all files, keeps the last entry per ID.
    Returns the signal dict or None if not found.
    """
    try:
        latest = None
        if not os.path.isdir(SIGNAL_LOG_DIR):
            return None

        for fname in sorted(os.listdir(SIGNAL_LOG_DIR)):
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(SIGNAL_LOG_DIR, fname)
            with open(fpath) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if obj.get("id") == signal_id:
                            latest = obj
                    except json.JSONDecodeError:
                        continue
        return latest
    except Exception:
        return None
