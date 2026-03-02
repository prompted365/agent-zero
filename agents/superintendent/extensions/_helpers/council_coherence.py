"""
Lane C Coherence Gate — governance council activation detection + escalation.

Evaluates whether the current conversation context activates multiple governance
councils from different tension clusters. When it does and the incompatibility
score exceeds the threshold, emits a LOCK candidate for human review.

Integration:
  - Called from _10_tricameral_router.py when a Lane C fingerprint is detected
  - Reads council metadata from JSONL (cached at module level)
  - Uses NaiveSurveillance decompose() for archetype activation detection
  - Computes pairwise incompatibility from cached council embeddings
  - Writes boundary witness records via governance_witness.py

The gate does NOT block execution — it flags for review. The LOCK mechanism
is advisory (same pattern as drift tracker LOCK candidates).
"""

import json
import logging
import math
import os
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_workspace = os.environ.get("WORKSPACE_DIR", "/workspace/operationTorque")
_COUNCILS_JSONL = os.path.join(
    _workspace, "priors", "governance_councils", "councils.jsonl"
)
_RUVECTOR_URL = os.environ.get("RUVECTOR_URL", "http://crawlset-ruvector:6333")

# Thresholds (matching incompatibility.py)
INCOMPATIBILITY_LOCK_THRESHOLD = 0.40
MIN_ACTIVATED_COUNCILS = 2
MIN_AMPLITUDE_FOR_ACTIVATION = 0.10  # council's linked archetype amplitude floor

# Module-level cache
_councils: Optional[list[dict]] = None
_council_embeddings: Optional[dict[str, list[float]]] = None
_archetype_to_councils: Optional[dict[str, list[dict]]] = None


@dataclass
class CoherenceResult:
    """Result of the Lane C coherence evaluation."""
    activated_councils: list[dict] = field(default_factory=list)
    incompatibility_scores: list[dict] = field(default_factory=list)
    max_incompatibility: float = 0.0
    cross_cluster: bool = False
    is_lock_candidate: bool = False
    decision: str = "coherence_pass"  # coherence_pass | coherence_fail | escalate_lock


def _load_councils() -> list[dict]:
    """Load and cache council metadata from JSONL."""
    global _councils
    if _councils is not None:
        return _councils

    _councils = []
    try:
        if not os.path.exists(_COUNCILS_JSONL):
            logger.warning(f"Councils JSONL not found: {_COUNCILS_JSONL}")
            return _councils
        with open(_COUNCILS_JSONL) as f:
            for line in f:
                line = line.strip()
                if line:
                    _councils.append(json.loads(line))
    except Exception as e:
        logger.warning(f"Failed to load councils: {e}")
        _councils = []

    return _councils


def _build_archetype_index() -> dict[str, list[dict]]:
    """Build archetype → council mapping from council metadata."""
    global _archetype_to_councils
    if _archetype_to_councils is not None:
        return _archetype_to_councils

    councils = _load_councils()
    _archetype_to_councils = {}
    for c in councils:
        for ref in c["links"]["archetype_refs"]:
            arch = ref["archetype"]
            _archetype_to_councils.setdefault(arch, []).append({
                "council_id": c["id"],
                "number": c["number"],
                "clusters": c["links"]["cluster_refs"],
                "archetype": arch,
                "confidence": ref["confidence"],
            })

    return _archetype_to_councils


def _fetch_council_embeddings() -> dict[str, list[float]]:
    """Fetch council embeddings from RuVector (cached at module level)."""
    global _council_embeddings
    if _council_embeddings is not None:
        return _council_embeddings

    _council_embeddings = {}
    try:
        payload = json.dumps({
            "query": "governance council tension",
            "collection": "governance_councils",
            "limit": 50,
            "include_vectors": True,
        }).encode()
        req = urllib.request.Request(
            f"{_RUVECTOR_URL}/search", data=payload, method="POST"
        )
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())

        for doc in result.get("results", []):
            doc_id = doc.get("id", "")
            vector = doc.get("vector") or doc.get("embedding")
            if doc_id.startswith("council_") and vector:
                council_id = doc_id[len("council_"):]
                _council_embeddings[council_id] = vector
    except Exception as e:
        logger.warning(f"Failed to fetch council embeddings: {e}")

    return _council_embeddings


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """1 - cosine_similarity. Range [0, 2], typically [0, 1] for normalized vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 1.0
    return 1.0 - (dot / (norm_a * norm_b))


def evaluate_coherence(
    archetype_amplitudes: dict[str, float],
    trace_id: str = "",
) -> CoherenceResult:
    """
    Evaluate governance council coherence given current archetype amplitudes.

    Args:
        archetype_amplitudes: Dict of {archetype_name: amplitude} from surveillance decompose().
            Amplitudes are normalized 0-1 values per archetype.
        trace_id: Per-monologue trace ID for witness record correlation.

    Returns:
        CoherenceResult with activated councils, incompatibility scores, and escalation decision.
    """
    result = CoherenceResult()

    # Build archetype→council index
    arch_index = _build_archetype_index()
    if not arch_index:
        return result

    # Find activated councils: archetype amplitude above threshold
    seen_councils = {}  # council_id → best activation
    for archetype, amplitude in archetype_amplitudes.items():
        if amplitude < MIN_AMPLITUDE_FOR_ACTIVATION:
            continue
        if archetype not in arch_index:
            continue
        for council_entry in arch_index[archetype]:
            cid = council_entry["council_id"]
            effective_amplitude = amplitude * council_entry["confidence"]
            if cid not in seen_councils or effective_amplitude > seen_councils[cid]["amplitude"]:
                seen_councils[cid] = {
                    "council_id": cid,
                    "number": council_entry["number"],
                    "clusters": council_entry["clusters"],
                    "amplitude": round(effective_amplitude, 4),
                    "archetype": archetype,
                }

    result.activated_councils = sorted(
        seen_councils.values(), key=lambda x: x["amplitude"], reverse=True
    )

    # Need at least 2 activated councils to evaluate coherence
    if len(result.activated_councils) < MIN_ACTIVATED_COUNCILS:
        result.decision = "coherence_pass"
        return result

    # Check cross-cluster activation
    all_clusters = set()
    per_council_clusters = []
    for ac in result.activated_councils:
        clusters = set(ac["clusters"])
        per_council_clusters.append(clusters)
        all_clusters.update(clusters)

    # Cross-cluster if any pair of councils shares no clusters
    result.cross_cluster = False
    for i in range(len(per_council_clusters)):
        for j in range(i + 1, len(per_council_clusters)):
            if not per_council_clusters[i] & per_council_clusters[j]:
                result.cross_cluster = True
                break
        if result.cross_cluster:
            break

    # Compute pairwise incompatibility scores using embeddings
    embeddings = _fetch_council_embeddings()
    if embeddings:
        activated_ids = [ac["council_id"] for ac in result.activated_councils]
        for i, id_a in enumerate(activated_ids):
            for id_b in activated_ids[i + 1:]:
                if id_a in embeddings and id_b in embeddings:
                    score = _cosine_distance(embeddings[id_a], embeddings[id_b])
                    num_a = seen_councils[id_a]["number"]
                    num_b = seen_councils[id_b]["number"]
                    interpretation = (
                        "aligned" if score < 0.15
                        else "complementary_tension" if score < INCOMPATIBILITY_LOCK_THRESHOLD
                        else "structural_opposition"
                    )
                    result.incompatibility_scores.append({
                        "pair": [num_a, num_b],
                        "score": round(score, 4),
                        "interpretation": interpretation,
                    })
                    if score > result.max_incompatibility:
                        result.max_incompatibility = score

    # Escalation decision
    if result.max_incompatibility >= INCOMPATIBILITY_LOCK_THRESHOLD and result.cross_cluster:
        result.is_lock_candidate = True
        result.decision = "escalate_lock"
    elif result.cross_cluster or result.max_incompatibility >= 0.30:
        result.decision = "coherence_fail"
    else:
        result.decision = "coherence_pass"

    # Write witness record
    try:
        from _helpers.governance_witness import record_witness
        record_witness(
            decision=result.decision,
            trigger_councils=result.activated_councils,
            incompatibility_scores=result.incompatibility_scores,
            cross_cluster=result.cross_cluster,
            trace_id=trace_id,
            outcome=(
                f"LOCK candidate (max_incompat={result.max_incompatibility:.3f})"
                if result.is_lock_candidate
                else f"decision={result.decision} max_incompat={result.max_incompatibility:.3f}"
            ),
        )
    except Exception as e:
        logger.warning(f"Witness record failed: {e}")

    return result


def format_coherence_injection(result: CoherenceResult) -> Optional[str]:
    """
    Format coherence evaluation for context injection.

    Returns a short block for the TRICAM context surface, or None if no signal.
    """
    if not result.activated_councils or result.decision == "coherence_pass":
        return None

    parts = ["\n[GOVERNANCE COHERENCE]"]

    council_strs = []
    for ac in result.activated_councils[:4]:
        council_strs.append(
            f"  #{ac['number']} ({', '.join(ac['clusters'][:2])}) amp={ac['amplitude']:.2f}"
        )
    parts.append(f"{len(result.activated_councils)} councils activated:")
    parts.extend(council_strs)

    if result.incompatibility_scores:
        max_pair = max(result.incompatibility_scores, key=lambda x: x["score"])
        parts.append(
            f"Max incompatibility: #{max_pair['pair'][0]} vs #{max_pair['pair'][1]} "
            f"= {max_pair['score']:.3f} ({max_pair['interpretation']})"
        )

    if result.cross_cluster:
        parts.append("Cross-cluster activation detected.")

    if result.is_lock_candidate:
        parts.append("LOCK CANDIDATE — structurally incompatible councils co-activated.")

    parts.append("[/GOVERNANCE COHERENCE]")
    return "\n".join(parts)
