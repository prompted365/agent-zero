"""
Epitaph Store — SQLite WAL durable persistence for epitaph governance events.

Epitaph creation is a governance event (PRIMITIVE/AUDIT). Embedding is indexing
for retrieval. Embedding failure must NEVER prevent epitaph persistence.

Three tables:
  - epitaph_events: mint ledger (every mint persisted before indexing)
  - embedding_queue: pending embeddings (backfill drains, calls embedder, writes to stores)
  - epitaph_acks: indexed confirmations (which store, when, plane_id)

ENFORCEMENT RULE — NO TOOL BOUNDARY:
  Epitaph minting is NOT a `code_execution_tool` deliverable. It is an internal
  extension-side write (direct SQLite transaction), immune to Publication Vector
  Gate classification. The motivation gate classifies file creation as "deliverable"
  — under PRESTIGE teeth, even governance files get blocked. Mint bypasses this
  entirely: it runs as a direct `sqlite3.connect()` in the extension process,
  never crossing the tool execution boundary where the physics gate enforces.
  If mint fails → PRIMITIVE BEACON (also emitted out-of-band via signal_emitter,
  not via tool call).

DB: Separate from Astragals (Rust) and Nautilus (Rust). Same directory, different
files. Justification: cross-runtime isolation (Python vs Rust), schema independence
(transport vs governance minting), blast radius (schema migration in one doesn't
affect the other), consistent with existing nautilus_economy.sqlite pattern.
"""

import os
import json
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.environ.get(
    "EPITAPH_STORE_DB",
    "/workspace/operationTorque/audit-logs/economy/epitaph_store.sqlite",
)

_SCHEMA_VERSION = 1

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS epitaph_events (
    epitaph_id TEXT PRIMARY KEY,
    tic_ref TEXT,
    conformation_hash TEXT,
    workflow_trace TEXT,
    trigger_kind TEXT NOT NULL,
    trigger_subsystem TEXT,
    trigger_reason_code TEXT,
    band TEXT DEFAULT 'COGNITIVE',
    worldline TEXT DEFAULT 'primary',
    lifecycle_state TEXT DEFAULT 'proto',
    event_surface TEXT DEFAULT 'ecotone_gate',
    context_shape TEXT,
    collapse_mode TEXT,
    corrective_disposition TEXT,
    trigger_signature TEXT,
    drift_band TEXT,
    weight REAL DEFAULT 0.6,
    failure_code TEXT,
    source TEXT,
    source_event TEXT,
    intent_snapshot TEXT,
    cause_chain TEXT,
    plane_id TEXT,
    dedupe_hash TEXT,
    birth_conformation TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS embedding_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epitaph_id TEXT NOT NULL REFERENCES epitaph_events(epitaph_id),
    plane_id TEXT NOT NULL,
    target_store TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    last_attempt_at TEXT,
    last_error TEXT,
    embedded_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS epitaph_acks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epitaph_id TEXT NOT NULL REFERENCES epitaph_events(epitaph_id),
    store TEXT NOT NULL,
    plane_id TEXT NOT NULL,
    doc_id TEXT,
    acked_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eq_status ON embedding_queue(status);
CREATE INDEX IF NOT EXISTS idx_eq_epitaph ON embedding_queue(epitaph_id);
CREATE INDEX IF NOT EXISTS idx_ea_epitaph ON epitaph_acks(epitaph_id);
CREATE INDEX IF NOT EXISTS idx_ee_lifecycle ON epitaph_events(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_ee_dedupe ON epitaph_events(dedupe_hash);
"""

_initialized = False


@contextmanager
def _get_db():
    """WAL-mode SQLite connection with auto-commit."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_tables():
    """Create tables if they don't exist. Idempotent."""
    global _initialized
    if _initialized:
        return
    with _get_db() as conn:
        conn.executescript(_CREATE_TABLES)
    _initialized = True


def mint_epitaph(
    epitaph_id: str,
    trigger_kind: str,
    context_shape: str = "unclassified",
    collapse_mode: str = "",
    corrective_disposition: str = "",
    trigger_signature: str = "",
    drift_band: str = "medium",
    weight: float = 0.6,
    failure_code: str = "",
    source: str = "",
    source_event: str = "",
    trigger_subsystem: str = "",
    trigger_reason_code: str = "",
    band: str = "COGNITIVE",
    worldline: str = "primary",
    lifecycle_state: str = "proto",
    event_surface: str = "ecotone_gate",
    intent_snapshot: dict | None = None,
    cause_chain: list | None = None,
    plane_id: str = "",
    dedupe_hash: str = "",
    birth_conformation: dict | None = None,
    tic_ref: str = "",
    conformation_hash: str = "",
    workflow_trace: list | None = None,
) -> bool:
    """Mint an epitaph to the durable WAL store.

    This ALWAYS succeeds (barring disk full / fs read-only). Called BEFORE
    any embedding or RuVector persistence attempt. Returns True on success.

    event_surface: Where the mint was triggered from. Closed vocabulary:
        ecotone_gate | motivation_gate | starvation_death | fork_reprimand | manual
    cause_chain: Bounded list of {kind, id, evidence_ref} linking signals/traces
        that led to this epitaph. Not free prose — structured provenance.
    """
    try:
        _ensure_tables()
        now = datetime.now(timezone.utc).isoformat()
        with _get_db() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO epitaph_events (
                    epitaph_id, tic_ref, conformation_hash, workflow_trace,
                    trigger_kind, trigger_subsystem, trigger_reason_code,
                    band, worldline, lifecycle_state, event_surface,
                    context_shape, collapse_mode, corrective_disposition,
                    trigger_signature, drift_band, weight, failure_code,
                    source, source_event, intent_snapshot, cause_chain,
                    plane_id, dedupe_hash, birth_conformation,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?
                )""",
                (
                    epitaph_id,
                    tic_ref,
                    conformation_hash,
                    json.dumps(workflow_trace or []),
                    trigger_kind,
                    trigger_subsystem,
                    trigger_reason_code,
                    band,
                    worldline,
                    lifecycle_state,
                    event_surface,
                    context_shape,
                    collapse_mode,
                    corrective_disposition,
                    trigger_signature,
                    drift_band,
                    weight,
                    failure_code,
                    source,
                    source_event,
                    json.dumps(intent_snapshot) if intent_snapshot else None,
                    json.dumps(cause_chain) if cause_chain else None,
                    plane_id,
                    dedupe_hash,
                    json.dumps(birth_conformation) if birth_conformation else None,
                    now,
                    now,
                ),
            )
        return True
    except Exception as e:
        print(f"[epitaph_store] MINT FAILED: {e}")
        return False


def enqueue_embedding(
    epitaph_id: str, plane_id: str, target_store: str = "ruvector"
) -> bool:
    """Add an epitaph to the embedding queue for async indexing."""
    try:
        _ensure_tables()
        now = datetime.now(timezone.utc).isoformat()
        with _get_db() as conn:
            conn.execute(
                """INSERT INTO embedding_queue
                   (epitaph_id, plane_id, target_store, status, created_at)
                   VALUES (?, ?, ?, 'pending', ?)""",
                (epitaph_id, plane_id, target_store, now),
            )
        return True
    except Exception:
        return False


def record_ack(
    epitaph_id: str, store: str, plane_id: str, doc_id: str = ""
) -> bool:
    """Record that an epitaph was successfully indexed in a store."""
    try:
        _ensure_tables()
        now = datetime.now(timezone.utc).isoformat()
        with _get_db() as conn:
            conn.execute(
                """INSERT INTO epitaph_acks
                   (epitaph_id, store, plane_id, doc_id, acked_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (epitaph_id, store, plane_id, doc_id, now),
            )
            conn.execute(
                """UPDATE embedding_queue
                   SET status='embedded', embedded_at=?
                   WHERE epitaph_id=? AND target_store=?
                   AND status='pending'""",
                (now, epitaph_id, store),
            )
        return True
    except Exception:
        return False


def mark_embedding_failed(
    epitaph_id: str, target_store: str, error: str = ""
) -> bool:
    """Mark an embedding queue entry as failed."""
    try:
        _ensure_tables()
        now = datetime.now(timezone.utc).isoformat()
        with _get_db() as conn:
            conn.execute(
                """UPDATE embedding_queue
                   SET status='failed', attempts=attempts+1,
                       last_attempt_at=?, last_error=?
                   WHERE epitaph_id=? AND target_store=?
                   AND status IN ('pending', 'failed')""",
                (now, error[:500], epitaph_id, target_store),
            )
        return True
    except Exception:
        return False


def get_pending_embeddings(limit: int = 50) -> list[dict]:
    """Get pending embedding queue entries for backfill worker."""
    try:
        _ensure_tables()
        with _get_db() as conn:
            rows = conn.execute(
                """SELECT eq.id AS queue_id, eq.epitaph_id, eq.plane_id,
                          eq.target_store, eq.attempts,
                          ee.context_shape, ee.collapse_mode,
                          ee.trigger_signature, ee.failure_code, ee.weight,
                          ee.drift_band, ee.source, ee.source_event,
                          ee.birth_conformation, ee.corrective_disposition,
                          ee.dedupe_hash
                   FROM embedding_queue eq
                   JOIN epitaph_events ee ON eq.epitaph_id = ee.epitaph_id
                   WHERE eq.status IN ('pending', 'failed')
                   AND eq.attempts < 5
                   ORDER BY eq.created_at ASC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def get_epitaph_by_dedupe(dedupe_hash: str) -> dict | None:
    """Check if an epitaph with this dedupe hash already exists."""
    try:
        _ensure_tables()
        with _get_db() as conn:
            row = conn.execute(
                "SELECT * FROM epitaph_events WHERE dedupe_hash=?",
                (dedupe_hash,),
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def update_lifecycle(epitaph_id: str, new_state: str) -> bool:
    """Update the lifecycle state of an epitaph.

    Valid states: proto, chorus_eligible, chorus_active, silenced.
    """
    valid = {"proto", "chorus_eligible", "chorus_active", "silenced"}
    if new_state not in valid:
        return False
    try:
        _ensure_tables()
        now = datetime.now(timezone.utc).isoformat()
        with _get_db() as conn:
            conn.execute(
                "UPDATE epitaph_events SET lifecycle_state=?, updated_at=? WHERE epitaph_id=?",
                (new_state, now, epitaph_id),
            )
        return True
    except Exception:
        return False


def get_stats() -> dict:
    """Get summary stats for telemetry/observatory."""
    try:
        _ensure_tables()
        with _get_db() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM epitaph_events"
            ).fetchone()[0]
            proto = conn.execute(
                "SELECT COUNT(*) FROM epitaph_events WHERE lifecycle_state='proto'"
            ).fetchone()[0]
            chorus = conn.execute(
                "SELECT COUNT(*) FROM epitaph_events WHERE lifecycle_state IN ('chorus_eligible', 'chorus_active')"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM embedding_queue WHERE status='pending'"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM embedding_queue WHERE status='failed'"
            ).fetchone()[0]
            acked = conn.execute(
                "SELECT COUNT(*) FROM epitaph_acks"
            ).fetchone()[0]
            return {
                "total_epitaphs": total,
                "proto": proto,
                "chorus_eligible_or_active": chorus,
                "pending_embeddings": pending,
                "failed_embeddings": failed,
                "total_acks": acked,
            }
    except Exception:
        return {}
