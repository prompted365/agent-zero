"""
Perception Lock — Epitaph CRUD for structured invariant objects in RuVector.

Epitaphs are NOT coaching paragraphs. They are structured invariant objects
where the real data lives in metadata fields (collapse_mode, corrective_disposition,
trigger_signature, drift_band, recurrence_count). The `text` field is a brief
invariant description used only for embedding search. Prose is never stored,
never retrieved — it is generated fresh each time by the Ghost Chorus from
structural invariants.

DIP-384 (2026-02-27): Epitaph creation is a governance event. Embedding is
indexing for retrieval. Embedding failure NEVER prevents epitaph persistence.
All mints go to the durable WAL store first, then RuVector best-effort.
Silent failures replaced with Siren signal emission.

Used by:
  - _65_epitaph_extraction.py (ecotone failures → invariant objects)
  - _45_ghost_chorus.py (retrieve invariant fields for synthesis)
  - _60_ecotone_integrity.py (decay on successful use)
"""

import math
import os
import json
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone

RUVECTOR_URL = os.environ.get("RUVECTOR_URL", "http://host.docker.internal:6334")
COLLECTION = os.environ.get("RUVECTOR_MOGUL_COLLECTION", "mogul_memory")

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

# Plane registry path (DIP-384)
_PLANE_REGISTRY_PATHS = [
    "/workspace/operationTorque/config/embedding_planes.json",
    os.path.join(os.path.dirname(__file__), "../../../../config/embedding_planes.json"),
]


def _get_active_plane_id() -> str:
    """Read the active plane ID from the plane registry."""
    try:
        for path in _PLANE_REGISTRY_PATHS:
            if os.path.isfile(path):
                with open(path) as f:
                    reg = json.load(f)
                return reg.get("active_plane", "unknown")
    except Exception:
        pass
    return "unknown"


def _emit_epitaph_signal(
    event_tag: str,
    kind: str,
    band: str,
    signature: str,
    summary: str,
    volume: int = 40,
    checks: list[str] | None = None,
    trace_id: str | None = None,
):
    """Emit a Siren signal for epitaph persistence events."""
    try:
        from _helpers.signal_emitter import emit_signal, make_dedup_signal_id
        sig_id = make_dedup_signal_id("epitaph_persistence", event_tag)
        emit_signal(
            signal_id=sig_id,
            kind=kind,
            band=band,
            subsystem="epitaph_persistence",
            source="perception_lock.py:create_epitaph",
            signature=signature,
            volume=volume,
            summary=summary,
            suggested_checks=checks or [],
            trace_id=trace_id,
        )
    except Exception:
        pass


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


def get_epitaph_pool_depth(
    embedding: list[float] | None = None,
    min_weight: float = 0.1,
) -> int:
    """
    Count active epitaphs in the pool.

    If an embedding is provided (preferred), queries RuVector with a broad
    search and counts type=epitaph results. Without embedding, attempts a
    dimension-matched zero-vector probe from collection metadata.

    Used by the chorus to determine abstraction level:
    1-3 = specific, 4-8 = composite, 9+ = ambient.

    Returns 0 on any failure — caller degrades gracefully.
    """
    try:
        if embedding is None:
            # Attempt to build a probe vector of correct dimension
            try:
                col_info = _ruvector_get(f"/collections/{COLLECTION}")
                dim = col_info.get("dimension", 384)
            except Exception:
                dim = 384
            embedding = [0.001] * dim  # Near-zero but non-zero to avoid NaN

        search_result = _ruvector_post("/search", {
            "embedding": embedding,
            "top_k": 100,  # Overfetch to count pool
            "collection": COLLECTION,
        }, timeout=5)
        count = 0
        for r in search_result.get("results", []):
            meta = r.get("metadata") or {}
            if meta.get("type") == "epitaph":
                eff_weight = meta.get("effective_weight", 0.0)
                if eff_weight >= min_weight:
                    count += 1
        return count
    except Exception:
        return 0


def _compute_conformation_fingerprint(birth_conformation: dict | None) -> dict:
    """Compute a lightweight conformation fingerprint for shape-proximity methylation.

    The fingerprint captures the folded shape of the system at failure time.
    During retrieval, the current system shape is compared against this
    fingerprint — when the shapes diverge, the epitaph gets methylated.

    Shape dimensions:
      - active_signal_bands: which frequency bands have active signals
      - total_signal_volume: aggregate pressure on the system
      - subsystems_active: which subsystems are signaling
      - drift_band: the tension level at failure
      - context_shape: categorical shape label
    """
    if not birth_conformation:
        return {}

    signals = birth_conformation.get("active_signals", [])
    bands_active = sorted(set(s.get("band", "") for s in signals))
    subsystems = sorted(set(s.get("subsystem", "") for s in signals))
    total_vol = sum(s.get("volume", 0) for s in signals)

    return {
        "signal_count": len(signals),
        "bands_active": bands_active,
        "subsystems_active": subsystems,
        "total_volume": total_vol,
        "warrant_count": len(birth_conformation.get("active_warrants", [])),
        "cogpr_count": len(birth_conformation.get("pending_cogprs", [])),
    }


def conformation_distance(fp_a: dict, fp_b: dict) -> float:
    """Compute distance between two conformation fingerprints.

    Returns 0.0 (identical shape) to 1.0 (completely different shape).
    Uses Jaccard distance on categorical sets + normalized scalar differences.
    """
    if not fp_a or not fp_b:
        return 0.5  # Unknown shape → neutral distance

    # Jaccard distance on band sets
    bands_a = set(fp_a.get("bands_active", []))
    bands_b = set(fp_b.get("bands_active", []))
    if bands_a or bands_b:
        band_jaccard = 1.0 - len(bands_a & bands_b) / max(len(bands_a | bands_b), 1)
    else:
        band_jaccard = 0.0

    # Jaccard distance on subsystem sets
    subs_a = set(fp_a.get("subsystems_active", []))
    subs_b = set(fp_b.get("subsystems_active", []))
    if subs_a or subs_b:
        sub_jaccard = 1.0 - len(subs_a & subs_b) / max(len(subs_a | subs_b), 1)
    else:
        sub_jaccard = 0.0

    # Normalized scalar differences
    vol_a = fp_a.get("total_volume", 0)
    vol_b = fp_b.get("total_volume", 0)
    max_vol = max(vol_a, vol_b, 1)
    vol_diff = abs(vol_a - vol_b) / max_vol

    sig_a = fp_a.get("signal_count", 0)
    sig_b = fp_b.get("signal_count", 0)
    max_sig = max(sig_a, sig_b, 1)
    sig_diff = abs(sig_a - sig_b) / max_sig

    # Weighted combination
    return min(1.0, band_jaccard * 0.3 + sub_jaccard * 0.3 + vol_diff * 0.2 + sig_diff * 0.2)


def create_epitaph(
    embedding: list[float] | None,
    context_shape: str,
    collapse_mode: str,
    corrective_disposition: str,
    trigger_signature: str,
    drift_band: str,
    weight: float,
    failure_code: str,
    source: str,
    source_event: str,
    birth_conformation: dict | None = None,
    event_surface: str = "ecotone_gate",
    cause_chain: list | None = None,
) -> str | None:
    """
    Create or deduplicate an epitaph.

    DIP-384 flow (2026-02-27):
    1. Mint to WAL store FIRST (always succeeds — governance event)
    2. Enqueue for embedding backfill
    3. If embedding provided, try immediate RuVector write (best-effort)
    4. Returns doc_id regardless of RuVector success

    Embedding is now optional (None). When None, the epitaph is minted
    to the WAL store and queued for backfill. RuVector write is skipped.

    Deduplication uses sha256(failure_code|context_shape|collapse_mode)[:16].
    """
    context_shape = _validate_context_shape(context_shape)
    birth_fp = _compute_conformation_fingerprint(birth_conformation)

    dedupe_hash = hashlib.sha256(
        f"{failure_code}|{context_shape}|{collapse_mode}".encode()
    ).hexdigest()[:16]

    doc_id = f"epitaph:{failure_code.lower()}:{dedupe_hash}"
    now = datetime.now(timezone.utc).isoformat()
    plane_id = _get_active_plane_id()

    # ── Step 1: Mint to WAL store FIRST (privileged, bypasses physics gate) ──
    try:
        from _helpers.epitaph_store import (
            mint_epitaph,
            enqueue_embedding,
            record_ack,
            get_epitaph_by_dedupe,
        )

        # Check WAL-level dedup
        existing = get_epitaph_by_dedupe(dedupe_hash)
        if existing:
            # Already minted — still try RuVector dedup/boost below
            pass
        else:
            mint_epitaph(
                epitaph_id=doc_id,
                trigger_kind=source,
                context_shape=context_shape,
                collapse_mode=collapse_mode,
                corrective_disposition=corrective_disposition,
                trigger_signature=trigger_signature,
                drift_band=drift_band,
                weight=weight,
                failure_code=failure_code,
                source=source,
                source_event=source_event,
                event_surface=event_surface,
                cause_chain=cause_chain,
                plane_id=plane_id,
                dedupe_hash=dedupe_hash,
                birth_conformation=birth_fp,
            )

        # Enqueue for embedding backfill
        enqueue_embedding(doc_id, plane_id, "ruvector")
    except Exception as e:
        # WAL mint failed — PRIMITIVE severity (should never happen)
        print(f"[perception_lock] WAL MINT FAILED: {e}")
        _emit_epitaph_signal(
            event_tag="wal_mint_failure",
            kind="BEACON",
            band="PRIMITIVE",
            signature="epitaph_wal_mint_failure",
            summary=f"Epitaph WAL mint failed: {str(e)[:200]}. "
            "Check disk space and SQLite WAL health.",
            volume=70,
            checks=["Check disk space", "Check epitaph_store.sqlite WAL health"],
        )

    # ── Step 2: If no embedding, return (WAL minted, backfill will handle) ──
    if embedding is None:
        try:
            from _helpers.chorus_telemetry import log_chorus_event
            log_chorus_event("epitaph_created", {
                "epitaph_id": doc_id,
                "context_shape": context_shape,
                "failure_code": failure_code,
                "source": source,
                "weight": weight,
                "wal_only": True,
            })
        except Exception:
            pass
        return doc_id

    # ── Step 3: Dimension guard (emit signal instead of silent None) ──
    try:
        col_info = _ruvector_get(f"/collections/{COLLECTION}")
        col_dim = col_info.get("dimension", 0)
        if col_dim > 0 and len(embedding) != col_dim:
            print(
                f"[perception_lock] DIMENSION MISMATCH: epitaph embedding="
                f"{len(embedding)}d, collection expects={col_dim}d. "
                f"WAL minted, backfill will re-embed at correct dimension."
            )
            _emit_epitaph_signal(
                event_tag=f"dim_mismatch_{len(embedding)}_{col_dim}",
                kind="BEACON",
                band="PRIMITIVE",
                signature="embedding_plane_drift",
                summary=(
                    f"Dimension mismatch: embedding={len(embedding)}d, "
                    f"collection expects={col_dim}d. Failure: {failure_code}. "
                    f"WAL minted, backfill will re-embed."
                ),
                volume=60,
                checks=[
                    "Check active plane in config/embedding_planes.json",
                    "Run embed-backfill.py to re-index at correct dimension",
                ],
            )
            try:
                from _helpers.chorus_telemetry import log_chorus_event
                log_chorus_event("epitaph_dimension_mismatch", {
                    "embedding_dim": len(embedding),
                    "collection_dim": col_dim,
                    "failure_code": failure_code,
                    "context_shape": context_shape,
                    "wal_minted": True,
                })
            except Exception:
                pass
            return doc_id  # WAL minted, embedding queued for backfill
    except Exception:
        pass  # RuVector unreachable — fall through to write attempt

    # ── Step 4: RuVector dedup check ──
    try:
        search_result = _ruvector_post("/search", {
            "embedding": embedding,
            "top_k": 20,
            "collection": COLLECTION,
        })
        for r in search_result.get("results", []):
            meta = r.get("metadata") or {}
            if meta.get("type") == "epitaph" and meta.get("dedupe_hash") == dedupe_hash:
                existing_id = r.get("id")
                if existing_id:
                    boost_epitaph(str(existing_id))
                    return str(existing_id)
    except (urllib.error.URLError, Exception):
        pass  # Search failed — proceed with creation

    # ── Step 5: RuVector write (best-effort) ──
    text = f"{context_shape}: {collapse_mode} under {trigger_signature}"
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
            "methylation_score": 0.0,
            "birth_conformation": birth_fp,
            "recurrence_count": 1,
            "dedupe_hash": dedupe_hash,
            "source": source,
            "source_event": source_event,
            "failure_code": failure_code,
            "plane_id": plane_id,
            "created_at": now,
            "last_seen": now,
        },
    }

    try:
        _ruvector_post("/documents", payload)
        # Record ACK in WAL store
        try:
            record_ack(doc_id, "ruvector", plane_id, doc_id)
        except Exception:
            pass
        # Telemetry
        try:
            from _helpers.chorus_telemetry import log_chorus_event
            log_chorus_event("epitaph_created", {
                "epitaph_id": doc_id,
                "context_shape": context_shape,
                "failure_code": failure_code,
                "source": source,
                "weight": weight,
                "ruvector_acked": True,
            })
        except Exception:
            pass
        return doc_id
    except (urllib.error.URLError, Exception) as e:
        # RuVector write failed — WAL minted, backfill will retry
        _emit_epitaph_signal(
            event_tag="ruvector_write_failure",
            kind="TENSION",
            band="COGNITIVE",
            signature="ruvector_epitaph_write_failure",
            summary=(
                f"RuVector write failed for {doc_id}: {str(e)[:200]}. "
                f"Epitaph WAL minted, backfill will retry."
            ),
            volume=40,
            checks=[
                "Check RuVector container health",
                "Run embed-backfill.py to retry indexing",
            ],
        )
        return doc_id  # WAL minted — return ID regardless


def retrieve_coaching_epitaphs(
    embedding: list[float],
    context_shape: str | None = None,
    top_k: int = 5,
    min_weight: float = 0.1,
    current_conformation: dict | None = None,
) -> list[dict]:
    """
    Retrieve epitaph invariant fields for chorus synthesis.

    Returns list of dicts with ALL metadata fields (collapse_mode,
    corrective_disposition, trigger_signature, drift_band, recurrence_count).

    Ranking: shape_match_bonus * 0.2 + effective_weight * score * expression_factor.

    Shape-proximity methylation: when `current_conformation` is provided,
    each epitaph's birth conformation is compared against the current shape.
    Epitaphs born under a similar conformation are expressed; those born
    under a distant conformation are silenced. This is the ASO targeting
    mechanism — epitaphs bind to complementary system shapes.
    """
    try:
        search_result = _ruvector_post("/search", {
            "embedding": embedding,
            "top_k": top_k * 3,  # overfetch for filtering
            "collection": COLLECTION,
            "include_vectors": True,  # for gaussian splat neighborhood scoring
        })
    except (urllib.error.URLError, Exception):
        return []

    # Hoist conformation fingerprint computation outside the loop — once per retrieval
    current_fp = _compute_conformation_fingerprint(current_conformation) if current_conformation else {}

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

        # Static methylation: accumulated from use/decay lifecycle
        static_methylation = meta.get("methylation_score", 0.0)

        # Dynamic methylation: shape-proximity targeting (ASO-like).
        # Compare the epitaph's birth conformation against the current system shape.
        # When shapes are similar (distance ≈ 0), dynamic methylation ≈ 0 (expressed).
        # When shapes diverge (distance → 1), dynamic methylation → 0.7 (silenced,
        # but never fully — distant conformations may still carry partial relevance).
        birth_fp = meta.get("birth_conformation", {})
        if current_fp and birth_fp:
            shape_dist = conformation_distance(birth_fp, current_fp)
            dynamic_methylation = shape_dist * 0.7  # cap at 0.7
        else:
            dynamic_methylation = 0.0  # no conformation data → fully expressed

        # Combined methylation: max of static and dynamic
        # Static captures "lesson has landed" (use-based).
        # Dynamic captures "wrong context for this lesson" (shape-based).
        methylation = max(static_methylation, dynamic_methylation)
        expression_factor = max(0.0, 1.0 - methylation)
        rank_score = (shape_bonus * 0.2 + eff_weight * score) * expression_factor

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
            "rank_score_linear": rank_score,  # preserve pre-splat score
            "_embedding": r.get("embedding"),  # for splat, not serialized
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
            "methylation_score": round(methylation, 4),
            "static_methylation": round(static_methylation, 4),
            "dynamic_methylation": round(dynamic_methylation, 4),
            "expression_factor": round(expression_factor, 4),
            "birth_fp_present": bool(birth_fp),
            "current_fp_present": bool(current_fp),
            "dynamic_methylation_applied": bool(current_fp and birth_fp),
            "birth_conformation": birth_fp if birth_fp else None,
            "age_days": round(age_days, 1),
            "hypothetical_age_weight": round(hypo_age_weight, 4),
            "last_seen": meta.get("last_seen", ""),
        })

    # Two-pass gaussian splat re-ranking — boost epitaphs in dense neighborhoods
    # Pass 1 already done: candidates have rank_score from methylation weighting.
    # Pass 2: when embeddings are available, compute true pairwise cosine distance
    # and blend gaussian neighborhood density into rank_score.
    _SPLAT_RADIUS = 0.6   # calibrated for 384D cosine distance space
    _SPLAT_SIGMA = 0.15
    _SPLAT_BLEND = 0.3
    has_embeddings = len(candidates) >= 2 and all(
        c.get("_embedding") and len(c["_embedding"]) > 0
        for c in candidates
    )
    if has_embeddings:
        # Compute pairwise gaussian-weighted neighborhood score
        splat_raw = {}
        for i, c in enumerate(candidates):
            ws, wt = 0.0, 0.0
            for j, n in enumerate(candidates):
                if i == j:
                    continue
                # True cosine distance
                vec_a, vec_b = c["_embedding"], n["_embedding"]
                dot = sum(a * b for a, b in zip(vec_a, vec_b))
                ma = math.sqrt(sum(a * a for a in vec_a))
                mb = math.sqrt(sum(b * b for b in vec_b))
                dist = 1.0 - (dot / (ma * mb)) if (ma > 0 and mb > 0) else 1.0
                if dist <= _SPLAT_RADIUS:
                    w = math.exp(-(dist * dist) / (2.0 * _SPLAT_SIGMA * _SPLAT_SIGMA))
                    ws += w * n["score"]
                    wt += w
            splat_raw[c["id"]] = ws / wt if wt > 0 else 0.0

        # Normalize to [0, 1]
        mx = max(splat_raw.values()) if splat_raw else 1.0
        splat_norm = {k: v / mx if mx > 0 else 0.0 for k, v in splat_raw.items()}

        # Blend into rank_score
        for c in candidates:
            splat = splat_norm.get(c["id"], 0.0)
            c["splat_score"] = round(splat, 4)
            c["rank_score"] = (1.0 - _SPLAT_BLEND) * c["rank_score_linear"] + _SPLAT_BLEND * splat

    # Clean up internal embedding field before returning
    for c in candidates:
        c.pop("_embedding", None)

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

    # Methylation: each successful use methylates the epitaph slightly.
    # The lesson is landing → gradually silence it so newer failures get priority.
    # methylation_score: 0.0 = fully expressed, 1.0 = fully silenced.
    # Increment: 0.05 per use, capped at 0.8 (never fully silenced by use alone).
    old_methyl = meta.get("methylation_score", 0.0)
    new_methyl = min(0.8, old_methyl + 0.05)

    meta["uses_count"] = uses
    meta["effective_weight"] = round(new_eff, 6)
    meta["methylation_score"] = round(new_methyl, 4)

    # Upsert back — refuse to zero the embedding
    embedding = doc.get("embedding")
    if not embedding or all(v == 0.0 for v in embedding[:10]):
        print(f"[perception_lock] decay_epitaph: missing/zero embedding for {doc_id}, aborting")
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

    # Demethylate on recurrence: the same failure recurred → the lesson
    # hasn't landed. Halve the methylation score to re-express the epitaph.
    old_methyl = meta.get("methylation_score", 0.0)
    meta["methylation_score"] = round(old_methyl * 0.5, 4)

    # Refuse to zero the embedding
    embedding = doc.get("embedding")
    if not embedding or all(v == 0.0 for v in embedding[:10]):
        print(f"[perception_lock] boost_epitaph: missing/zero embedding for {doc_id}, aborting")
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

        # Generate embedding — local first (DIP-384 sovereignty), then fallback
        text = f"{context_shape}: {collapse_mode} under {trigger_signature}"
        embedding = None

        # Priority 1: caller-provided embed_fn (testing)
        if embed_fn:
            embedding = embed_fn(text)

        # Priority 2: local Ollama embedder (sovereignty)
        if embedding is None:
            try:
                from _helpers.local_embedder import embed_text
                embedding = embed_text(text)
            except Exception:
                pass

        # Priority 3: external embedder via agent (fallback)
        if embedding is None and agent:
            try:
                from python.helpers.memory import Memory
                import asyncio
                db = asyncio.get_event_loop().run_until_complete(Memory.get(agent))
                embedding = list(db.db.embedding_function.embed_query(text))
            except Exception:
                pass

        # DIP-384: embedding=None is OK — WAL will still mint, backfill later
        if embedding and all(v == 0.0 for v in embedding[:10]):
            embedding = None  # Zero vectors are useless, treat as missing

        # Create epitaph (mints to WAL first, then RuVector best-effort)
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
