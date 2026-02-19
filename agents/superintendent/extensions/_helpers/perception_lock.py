"""
Perception Lock — Epitaph CRUD for structured invariant objects in RuVector.

Epitaphs are NOT coaching paragraphs. They are structured invariant objects
where the real data lives in metadata fields (collapse_mode, corrective_disposition,
trigger_signature, drift_band, recurrence_count). The `text` field is a brief
invariant description used only for embedding search. Prose is never stored,
never retrieved — it is generated fresh each time by the Ghost Chorus from
structural invariants.

Used by:
  - _65_epitaph_extraction.py (ecotone failures → invariant objects)
  - _45_ghost_chorus.py (retrieve invariant fields for synthesis)
  - _60_ecotone_integrity.py (decay on successful use)
"""

import os
import json
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone

RUVECTOR_URL = os.environ.get("RUVECTOR_URL", "http://host.docker.internal:6334")
COLLECTION = os.environ.get("RUVECTOR_MOGUL_COLLECTION", "mogul_memory")
DIMENSION = 384  # all-MiniLM-L6-v2 output dimension

# Controlled vocabulary for context_shape — closed set, no free-form.
VALID_CONTEXT_SHAPES = {
    "integration_gap",
    "early_collapse",
    "substrate_poverty",
    "performative_integration",
    "anchor_departure",
    "ungrounded_synthesis",
    "converging_constraints",
    "identity_pressure",
    "novel_territory",
    "steady_state",
    "unclassified",
}

# Journal sync state file
_JOURNAL_STATE_PATH = os.environ.get(
    "EPITAPH_JOURNAL_STATE",
    "/a0/usr/epitaph_journal_sync_state.json",
)


def _ruvector_post(endpoint: str, payload: dict, timeout: int = 10) -> dict:
    """POST JSON to RuVector and return parsed response."""
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{RUVECTOR_URL}{endpoint}",
        data=body,
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _ruvector_get(endpoint: str, timeout: int = 5) -> dict:
    """GET from RuVector and return parsed response."""
    req = urllib.request.Request(f"{RUVECTOR_URL}{endpoint}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _validate_context_shape(shape: str) -> str:
    """Map context_shape to controlled vocabulary. Default to 'unclassified'."""
    if shape in VALID_CONTEXT_SHAPES:
        return shape
    # Fuzzy mapping for common utility model guesses
    shape_lower = shape.lower().replace(" ", "_").replace("-", "_")
    if shape_lower in VALID_CONTEXT_SHAPES:
        return shape_lower
    return "unclassified"


def create_epitaph(
    embedding: list[float],
    context_shape: str,
    collapse_mode: str,
    corrective_disposition: str,
    trigger_signature: str,
    drift_band: str,
    weight: float,
    failure_code: str,
    source: str,
    source_event: str,
) -> str | None:
    """
    Create or deduplicate an epitaph in RuVector.

    Returns the epitaph document ID, or None on failure.
    Deduplication uses sha256(failure_code|context_shape|collapse_mode)[:16] —
    NO free text in the hash (free text creates near-duplicates forever).
    """
    context_shape = _validate_context_shape(context_shape)
    dedupe_hash = hashlib.sha256(
        f"{failure_code}|{context_shape}|{collapse_mode}".encode()
    ).hexdigest()[:16]

    # Search for existing epitaph with same dedupe_hash
    try:
        search_result = _ruvector_post("/search", {
            "embedding": embedding,
            "top_k": 20,
            "collection": COLLECTION,
        })
        for r in search_result.get("results", []):
            meta = r.get("metadata") or {}
            if meta.get("type") == "epitaph" and meta.get("dedupe_hash") == dedupe_hash:
                # Duplicate found — boost instead of creating
                existing_id = r.get("id")
                if existing_id:
                    boost_epitaph(str(existing_id))
                    return str(existing_id)
    except (urllib.error.URLError, Exception):
        pass  # Search failed — proceed with creation (may create duplicate, acceptable)

    # Build text field: brief invariant summary for embedding, NOT prose
    text = f"{context_shape}: {collapse_mode} under {trigger_signature}"
    now = datetime.now(timezone.utc).isoformat()
    doc_id = f"epitaph:{failure_code.lower()}:{dedupe_hash}"

    payload = {
        "id": doc_id,
        "text": text,
        "embedding": embedding,
        "collection": COLLECTION,
        "metadata": {
            "type": "epitaph",
            "locked": True,
            "lock_type": "perception",
            "context_shape": context_shape,
            "collapse_mode": collapse_mode,
            "corrective_disposition": corrective_disposition,
            "trigger_signature": trigger_signature,
            "drift_band": drift_band,
            "weight": weight,
            "uses_count": 0,
            "effective_weight": weight,
            "recurrence_count": 1,
            "dedupe_hash": dedupe_hash,
            "source": source,
            "source_event": source_event,
            "failure_code": failure_code,
            "created_at": now,
            "last_seen": now,
        },
    }

    try:
        _ruvector_post("/documents", payload)
        # Telemetry: epitaph_created
        try:
            from _helpers.chorus_telemetry import log_chorus_event
            log_chorus_event("epitaph_created", {
                "epitaph_id": doc_id,
                "context_shape": context_shape,
                "failure_code": failure_code,
                "source": source,
                "weight": weight,
            })
        except Exception:
            pass
        return doc_id
    except (urllib.error.URLError, Exception):
        return None


def retrieve_coaching_epitaphs(
    embedding: list[float],
    context_shape: str | None = None,
    top_k: int = 5,
    min_weight: float = 0.1,
) -> list[dict]:
    """
    Retrieve epitaph invariant fields for chorus synthesis.

    Returns list of dicts with ALL metadata fields (collapse_mode,
    corrective_disposition, trigger_signature, drift_band, recurrence_count).
    Sorted by shape_match_bonus * 0.2 + effective_weight * score.
    """
    try:
        search_result = _ruvector_post("/search", {
            "embedding": embedding,
            "top_k": top_k * 3,  # overfetch for filtering
            "collection": COLLECTION,
        })
    except (urllib.error.URLError, Exception):
        return []

    candidates = []
    for r in search_result.get("results", []):
        meta = r.get("metadata") or {}
        if meta.get("type") != "epitaph":
            continue
        eff_weight = meta.get("effective_weight", 0.0)
        if eff_weight < min_weight:
            continue

        score = r.get("score", 0.0)
        shape_bonus = 1.0 if (context_shape and meta.get("context_shape") == context_shape) else 0.0
        rank_score = shape_bonus * 0.2 + eff_weight * score

        # Temporal fields — logged for telemetry, NOT applied to scoring
        created = meta.get("created_at", "")
        age_days = 0.0
        if created:
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - created_dt).total_seconds() / 86400
            except (ValueError, TypeError):
                pass
        # Hypothetical age-adjusted weight — observed only, not used for rank_score
        hypo_age_weight = eff_weight * (0.98 ** age_days)

        candidates.append({
            "id": r.get("id"),
            "score": score,
            "rank_score": rank_score,
            "context_shape": meta.get("context_shape", "unclassified"),
            "collapse_mode": meta.get("collapse_mode", ""),
            "corrective_disposition": meta.get("corrective_disposition", ""),
            "trigger_signature": meta.get("trigger_signature", ""),
            "drift_band": meta.get("drift_band", "medium"),
            "recurrence_count": meta.get("recurrence_count", 1),
            "effective_weight": eff_weight,
            "weight": meta.get("weight", 0.5),
            "uses_count": meta.get("uses_count", 0),
            "failure_code": meta.get("failure_code", ""),
            "source": meta.get("source", ""),
            "age_days": round(age_days, 1),
            "hypothetical_age_weight": round(hypo_age_weight, 4),
            "last_seen": meta.get("last_seen", ""),
        })

    candidates.sort(key=lambda c: c["rank_score"], reverse=True)
    selected = candidates[:top_k]

    # Telemetry: emit epitaph_retrieved for each returned candidate
    try:
        from _helpers.chorus_telemetry import log_chorus_event
        for ep in selected:
            log_chorus_event("epitaph_retrieved", {
                "epitaph_id": ep["id"],
                "rank_score": ep["rank_score"],
                "age_days": ep["age_days"],
                "hypothetical_age_weight": ep["hypothetical_age_weight"],
                "effective_weight": ep["effective_weight"],
                "recurrence_count": ep["recurrence_count"],
            })
    except Exception:
        pass

    return selected


def decay_epitaph(doc_id: str) -> bool:
    """
    Decay an epitaph after successful use.
    Increments uses_count, recalculates effective_weight = weight * 0.95^uses_count.
    """
    try:
        doc = _ruvector_get(f"/documents/{doc_id}")
    except (urllib.error.URLError, Exception):
        return False

    meta = doc.get("metadata") or {}
    if meta.get("type") != "epitaph":
        return False

    uses = meta.get("uses_count", 0) + 1
    weight = meta.get("weight", 0.5)
    new_eff = weight * (0.95 ** uses)

    meta["uses_count"] = uses
    meta["effective_weight"] = round(new_eff, 6)

    # Upsert back — refuse to zero the embedding
    embedding = doc.get("embedding")
    if not embedding or all(v == 0.0 for v in embedding[:10]):
        logger.warning(f"decay_epitaph: missing/zero embedding for {doc_id}, aborting")
        return False
    payload = {
        "id": doc_id,
        "text": doc.get("text", ""),
        "embedding": embedding,
        "collection": COLLECTION,
        "metadata": meta,
    }
    try:
        _ruvector_post("/documents", payload)
        # Telemetry: epitaph_decayed
        try:
            from _helpers.chorus_telemetry import log_chorus_event
            created = meta.get("created_at", "")
            age_days = 0.0
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age_days = (datetime.now(timezone.utc) - created_dt).total_seconds() / 86400
                except (ValueError, TypeError):
                    pass
            log_chorus_event("epitaph_decayed", {
                "epitaph_id": doc_id,
                "new_effective_weight": round(new_eff, 6),
                "uses_count": uses,
                "age_days": round(age_days, 1),
            })
        except Exception:
            pass
        return True
    except (urllib.error.URLError, Exception):
        return False


def boost_epitaph(doc_id: str, boost: float = 0.05) -> bool:
    """
    Boost an epitaph when the same pattern recurs.
    Increases weight (cap 1.0), resets uses_count to 0, increments recurrence_count,
    updates last_seen. Recurring pattern = lesson hasn't landed yet.
    """
    try:
        doc = _ruvector_get(f"/documents/{doc_id}")
    except (urllib.error.URLError, Exception):
        return False

    meta = doc.get("metadata") or {}
    if meta.get("type") != "epitaph":
        return False

    weight = min(1.0, meta.get("weight", 0.5) + boost)
    recurrence = meta.get("recurrence_count", 1) + 1

    meta["weight"] = round(weight, 4)
    meta["uses_count"] = 0
    meta["effective_weight"] = round(weight, 4)
    meta["recurrence_count"] = recurrence
    meta["last_seen"] = datetime.now(timezone.utc).isoformat()

    # Refuse to zero the embedding
    embedding = doc.get("embedding")
    if not embedding or all(v == 0.0 for v in embedding[:10]):
        logger.warning(f"boost_epitaph: missing/zero embedding for {doc_id}, aborting")
        return False
    payload = {
        "id": doc_id,
        "text": doc.get("text", ""),
        "embedding": embedding,
        "collection": COLLECTION,
        "metadata": meta,
    }
    try:
        _ruvector_post("/documents", payload)
        # Telemetry: epitaph_boosted
        try:
            from _helpers.chorus_telemetry import log_chorus_event
            last_seen = meta.get("last_seen", "")
            days_since_last = 0.0
            if last_seen:
                try:
                    last_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                    days_since_last = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
                except (ValueError, TypeError):
                    pass
            log_chorus_event("epitaph_boosted", {
                "epitaph_id": doc_id,
                "new_weight": round(weight, 4),
                "recurrence_count": recurrence,
                "days_since_last": round(days_since_last, 1),
            })
        except Exception:
            pass
        return True
    except (urllib.error.URLError, Exception):
        return False


def sync_journal_epitaphs(
    journal_epitaph_path: str,
    agent=None,
    embed_fn=None,
) -> int:
    """
    Sync journal epitaphs from JSONL into RuVector.

    Reads epitaph_database.jsonl, tracks last synced line, and for each new entry:
    1. Calls utility model to extract structured fields
    2. Maps context_shape to controlled vocabulary
    3. Generates embedding from invariant text
    4. Calls create_epitaph() with source="journal"

    Requires either `agent` (for utility model + embedder) or `embed_fn` (for testing).
    Returns count of epitaphs synced.
    """
    if not os.path.isfile(journal_epitaph_path):
        return 0

    # Load sync state
    last_synced = 0
    if os.path.isfile(_JOURNAL_STATE_PATH):
        try:
            with open(_JOURNAL_STATE_PATH) as f:
                state = json.load(f)
            last_synced = state.get("last_synced_line", 0)
        except (json.JSONDecodeError, OSError):
            pass

    # Read journal JSONL
    try:
        with open(journal_epitaph_path) as f:
            lines = f.readlines()
    except OSError:
        return 0

    if len(lines) <= last_synced:
        return 0  # No new entries

    synced = 0
    for i, line in enumerate(lines[last_synced:], start=last_synced):
        line = line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Extract fields — journal entries may already have structured fields
        # or may need utility model extraction
        collapse_mode = entry.get("collapse_mode", "")
        corrective_disposition = entry.get("corrective_disposition", "")
        trigger_signature = entry.get("trigger_signature", "")
        context_shape = entry.get("context_shape", "unclassified")
        failure_code = entry.get("failure_code", "JOURNAL_OBSERVATION")

        # If fields are missing and we have an agent, call utility model
        if agent and not collapse_mode:
            try:
                import asyncio
                extraction_prompt = (
                    "Extract the structural pattern from this journal epitaph.\n\n"
                    f"Entry: {json.dumps(entry)}\n\n"
                    "Return ONLY valid JSON with these fields:\n"
                    '{\n'
                    '  "collapse_mode": "what went wrong — 3-5 words",\n'
                    '  "corrective_disposition": "what posture prevents this — one sentence",\n'
                    '  "trigger_signature": "what conditions trigger this — 3-5 words",\n'
                    '  "context_shape_guess": "best match from: integration_gap, early_collapse, '
                    'substrate_poverty, performative_integration, anchor_departure, '
                    'ungrounded_synthesis, converging_constraints, identity_pressure, '
                    'novel_territory"\n'
                    "}\n\nJSON only."
                )
                result = asyncio.get_event_loop().run_until_complete(
                    agent.call_utility_model(
                        system="You are a structural pattern extractor. Return ONLY valid JSON.",
                        message=extraction_prompt,
                        background=True,
                    )
                )
                if result:
                    import re
                    result = result.strip()
                    if result.startswith("```"):
                        result = re.sub(r"^```(?:json)?\s*", "", result)
                        result = re.sub(r"\s*```$", "", result)
                    parsed = json.loads(result)
                    collapse_mode = parsed.get("collapse_mode", "unknown_collapse")
                    corrective_disposition = parsed.get("corrective_disposition", "")
                    trigger_signature = parsed.get("trigger_signature", "unknown_trigger")
                    context_shape = _validate_context_shape(
                        parsed.get("context_shape_guess", "unclassified")
                    )
            except Exception:
                collapse_mode = entry.get("text", "unextracted journal observation")[:50]
                corrective_disposition = ""
                trigger_signature = "journal_entry"

        if not collapse_mode:
            collapse_mode = entry.get("text", "unextracted")[:50]
        if not trigger_signature:
            trigger_signature = "journal_entry"

        # Generate embedding
        text = f"{context_shape}: {collapse_mode} under {trigger_signature}"
        embedding = None
        if embed_fn:
            embedding = embed_fn(text)
        elif agent:
            try:
                from python.helpers.memory import Memory
                import asyncio
                db = asyncio.get_event_loop().run_until_complete(Memory.get(agent))
                embedding = list(db.db.embedding_function.embed_query(text))
            except Exception:
                embedding = [0.0] * DIMENSION

        if embedding is None:
            embedding = [0.0] * DIMENSION

        # Create epitaph
        source_event = f"journal_{os.path.basename(journal_epitaph_path)}_{i}"
        result = create_epitaph(
            embedding=embedding,
            context_shape=context_shape,
            collapse_mode=collapse_mode,
            corrective_disposition=corrective_disposition,
            trigger_signature=trigger_signature,
            drift_band="medium",
            weight=0.60,
            failure_code=failure_code,
            source="journal",
            source_event=source_event,
        )
        if result:
            synced += 1

    # Update sync state
    try:
        os.makedirs(os.path.dirname(_JOURNAL_STATE_PATH), exist_ok=True)
        with open(_JOURNAL_STATE_PATH, "w") as f:
            json.dump({"last_synced_line": len(lines)}, f)
    except OSError:
        pass

    return synced
