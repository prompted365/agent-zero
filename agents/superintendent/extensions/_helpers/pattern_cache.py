"""
Pattern Cache — Shared helper for priors pattern matching.

Loads Detect-tier patterns from compliance-modules/priors/ JSON files,
compiles a single regex alternation for efficient matching, and caches
the compiled matcher for reuse within the process lifetime.

Supports TriggerSpec v1: trigger_lexemes, trigger_phrases, negative_triggers
with weighted confidence and suppression checking.

Used by:
  - _55_quiver_drift_tracker.py (pattern anchoring in context)
  - _55_quiver_memory_sync.py (pattern tagging on memories)
"""

import os
import re
import json
import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)

PRIORS_DIR = os.environ.get(
    "PRIORS_MODULE_DIR",
    "/workspace/operationTorque/compliance-modules/priors",
)
SHAPES_PATH = os.environ.get(
    "ARCHETYPE_SHAPES_PATH",
    "/workspace/operationTorque/compliance-modules/archetype_shapes.json",
)

class PatternAnchor(NamedTuple):
    term: str
    module_id: str
    domain: str


# Module-level cache
_compiled_pattern: re.Pattern | None = None
_pattern_lookup: dict[str, PatternAnchor] = {}
_shape_term_map: dict[str, dict] = {}  # term → {"family": str, "label": str}

# Structured library caches (TriggerSpec v1)
_motif_by_trigger: dict[str, dict] = {}
_negative_triggers: dict[str, list[str]] = {}   # library_id → [negative strings]
_negative_patterns: dict[str, re.Pattern] = {}   # library_id → compiled negative regex
_library_entries: dict[str, dict] = {}           # library_id → full entry dict
_lineage_graph: dict[str, list[str]] = {}        # event_id → lineage_edges

# Default TriggerSpec weights
_DEFAULT_WEIGHTS = {"phrase": 1.0, "lexeme": 0.5, "feature": 0.7, "detect": 0.7}


def _load_modules() -> list[PatternAnchor]:
    """Walk priors directory and extract all detect-tier patterns."""
    anchors = []
    if not os.path.isdir(PRIORS_DIR):
        logger.warning(f"Pattern priors directory missing: {PRIORS_DIR}")
        return anchors
    for fname in sorted(os.listdir(PRIORS_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(PRIORS_DIR, fname)
        try:
            with open(fpath) as f:
                mod = json.load(f)
            module_id = mod.get("id", fname.replace(".json", ""))
            domain = mod.get("domain", "priors")
            for term in mod.get("patterns", {}).get("detect", []):
                anchors.append(PatternAnchor(term=term.lower(), module_id=module_id, domain=domain))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Skipping malformed priors module {fname}: {e}")
            continue
    return anchors


def _load_shape_map() -> dict[str, dict]:
    """Load term→archetype mapping from archetype_shapes.json."""
    if not os.path.isfile(SHAPES_PATH):
        logger.info(f"Archetype shapes file not found: {SHAPES_PATH}")
        return {}
    try:
        with open(SHAPES_PATH) as f:
            data = json.load(f)
        archetypes = data.get("archetypes", {})
        term_map = data.get("term_map", {})
        result = {}
        for term, family in term_map.items():
            arch = archetypes.get(family, {})
            result[term.lower()] = {
                "family": family,
                "label": arch.get("label", ""),
            }
        logger.info(f"Loaded {len(result)} term→archetype shape mappings")
        return result
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load archetype shapes: {e}")
        return {}


def _load_structured_libraries() -> tuple[dict[str, dict], list[PatternAnchor]]:
    """Load structured library entries keyed by trigger features + trigger_spec terms.

    Indexes three sources per entry (in priority order):
      1. trigger_spec.trigger_phrases (matched_via="phrase", confidence=1.0)
      2. trigger_spec.trigger_lexemes (matched_via="lexeme", confidence=0.5)
      3. trigger_features (matched_via="feature", confidence=0.7) — legacy compat

    Also builds the negative trigger side-map for suppression checking.

    Returns:
        (reverse_index, additional_anchors) where:
        - reverse_index maps trigger term → library info dict
        - additional_anchors are PatternAnchors for trigger_spec terms
          not already present in patterns.detect[]
    """
    result: dict[str, dict] = {}
    extra_anchors: list[PatternAnchor] = []
    if not os.path.isdir(PRIORS_DIR):
        return result, extra_anchors

    for fname in sorted(os.listdir(PRIORS_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(PRIORS_DIR, fname)
        try:
            with open(fpath) as f:
                mod = json.load(f)
            module_id = mod.get("id", fname.replace(".json", ""))
            domain = mod.get("domain", "priors")
            detect_terms = {t.lower() for t in mod.get("patterns", {}).get("detect", [])}

            for collection_key, id_field, type_label in [
                ("motifs", "motif_id", "motif"),
                ("concepts", "concept_id", "concept"),
                ("milestones", "event_id", "milestone"),
            ]:
                for entry in mod.get(collection_key, []):
                    entry_id = entry.get(id_field, "")
                    title = (
                        entry.get("title")
                        or entry.get("topic")
                        or entry.get("name", "")
                    )
                    base_info = {
                        "library_type": type_label,
                        "library_id": entry_id,
                        "title": title,
                    }

                    # Cache full entry for LINEAGE validation and enrichment
                    _library_entries[entry_id] = entry

                    # Build lineage adjacency graph for milestones
                    if collection_key == "milestones":
                        edges = entry.get("lineage_edges", [])
                        if edges:
                            _lineage_graph[entry_id] = edges

                    # Legacy trigger_features (lowest priority)
                    for trigger in entry.get("trigger_features", []):
                        key = trigger.lower()
                        if key not in result:
                            result[key] = {**base_info, "matched_via": "feature"}

                    # Topic/name as implicit trigger for concepts/milestones
                    if collection_key == "concepts":
                        topic = entry.get("topic", "").lower()
                        if topic and topic not in result:
                            result[topic] = {**base_info, "matched_via": "feature"}
                    elif collection_key == "milestones":
                        name = entry.get("name", "").lower()
                        if name and name not in result:
                            result[name] = {**base_info, "matched_via": "feature"}

                    # TriggerSpec v1 terms (overwrite features with richer typing)
                    spec = entry.get("trigger_spec")
                    if not spec:
                        continue

                    # trigger_phrases — highest confidence, always overwrite
                    for phrase in spec.get("trigger_phrases", []):
                        key = phrase.lower()
                        result[key] = {**base_info, "matched_via": "phrase"}
                        if key not in detect_terms:
                            extra_anchors.append(
                                PatternAnchor(term=key, module_id=module_id, domain=domain)
                            )

                    # trigger_lexemes — lower confidence, don't overwrite phrase
                    for lexeme in spec.get("trigger_lexemes", []):
                        key = lexeme.lower()
                        if key not in result:
                            result[key] = {**base_info, "matched_via": "lexeme"}
                        if key not in detect_terms:
                            extra_anchors.append(
                                PatternAnchor(term=key, module_id=module_id, domain=domain)
                            )

                    # Negative triggers → side-map for suppression
                    negatives = spec.get("negative_triggers", [])
                    if negatives:
                        lowered = [n.lower() for n in negatives]
                        _negative_triggers[entry_id] = lowered
                        escaped = [re.escape(n) for n in lowered]
                        _negative_patterns[entry_id] = re.compile(
                            "|".join(escaped), re.IGNORECASE
                        )

        except (json.JSONDecodeError, OSError):
            continue

    logger.info(
        f"Loaded {len(result)} structured library trigger mappings "
        f"({len(extra_anchors)} additional anchors from trigger_specs, "
        f"{len(_negative_triggers)} entries with negative triggers)"
    )
    return result, extra_anchors


def get_matcher() -> tuple[re.Pattern | None, dict[str, PatternAnchor]]:
    """Return compiled regex and lookup dict. Cached after first call."""
    global _compiled_pattern, _pattern_lookup, _shape_term_map
    if _compiled_pattern is not None:
        return _compiled_pattern, _pattern_lookup

    anchors = _load_modules()
    _shape_term_map = _load_shape_map()
    lib_index, extra_anchors = _load_structured_libraries()
    _motif_by_trigger.update(lib_index)

    # Merge trigger_spec anchors into the pattern set
    all_anchors = anchors + extra_anchors

    if not all_anchors:
        logger.warning(f"No pattern anchors loaded from {PRIORS_DIR}")
        return None, {}

    _pattern_lookup = {a.term: a for a in all_anchors}
    # Sort by length descending so longer patterns match first
    terms = sorted(_pattern_lookup.keys(), key=len, reverse=True)
    escaped = [re.escape(t) for t in terms]
    _compiled_pattern = re.compile("|".join(escaped), re.IGNORECASE)

    return _compiled_pattern, _pattern_lookup


def _check_suppression(
    text_lower: str, match_pos: int, library_id: str, token_radius: int = 48
) -> tuple[bool, str | None]:
    """Check if negative triggers suppress a match within the token radius window.

    Approximates token_radius as char_radius (5 chars/token average).
    """
    neg_pattern = _negative_patterns.get(library_id)
    if not neg_pattern:
        return False, None

    char_radius = token_radius * 5
    window_start = max(0, match_pos - char_radius)
    window_end = min(len(text_lower), match_pos + char_radius)
    window = text_lower[window_start:window_end]

    neg_match = neg_pattern.search(window)
    if neg_match:
        return True, neg_match.group(0)
    return False, None


def scan_text(text: str) -> list[dict]:
    """Scan text for priors pattern anchors. Returns list of match dicts.

    Each result dict contains:
        term, module_id, domain, position  — always present
        archetype_family, archetype_label  — if term has shape mapping
        library_type, library_id           — if term maps to structured library entry
        matched_via                        — "phrase" | "lexeme" | "feature" | "detect"
        confidence                         — 0.0–1.0 based on match type
        suppressed                         — True if negative trigger found nearby
        suppression_reason                 — the negative trigger string, or None
    """
    pattern, lookup = get_matcher()
    if pattern is None:
        return []

    text_lower = text.lower()
    seen = set()
    results = []
    for match in pattern.finditer(text_lower):
        term = match.group(0)
        if term in seen:
            continue
        seen.add(term)
        anchor = lookup.get(term)
        if anchor:
            entry = {
                "term": anchor.term,
                "module_id": anchor.module_id,
                "domain": anchor.domain,
                "position": match.start(),
            }
            shape = _shape_term_map.get(term)
            if shape:
                entry["archetype_family"] = shape["family"]
                entry["archetype_label"] = shape["label"]

            # Structured library enrichment + suppression
            lib = _motif_by_trigger.get(term)
            if lib:
                entry["library_type"] = lib["library_type"]
                entry["library_id"] = lib["library_id"]
                matched_via = lib.get("matched_via", "detect")
                entry["matched_via"] = matched_via
                entry["confidence"] = _DEFAULT_WEIGHTS.get(matched_via, 0.7)

                suppressed, reason = _check_suppression(
                    text_lower, match.start(), lib["library_id"]
                )
                entry["suppressed"] = suppressed
                entry["suppression_reason"] = reason
                if suppressed:
                    entry["confidence"] = 0.0
            else:
                entry["matched_via"] = "detect"
                entry["confidence"] = _DEFAULT_WEIGHTS["detect"]
                entry["suppressed"] = False
                entry["suppression_reason"] = None

            results.append(entry)
    return results


COMPILED_TRIGGERS_DIR = os.environ.get(
    "COMPILED_TRIGGERS_DIR",
    "/workspace/operationTorque/audit-logs/compiled_triggers",
)


def _emit_compiled_triggers(write_back: bool = False):
    """Generate the compiled_triggers artifact from the in-memory trigger index.

    By default, writes a single artifact to audit-logs/compiled_triggers/latest.json.
    This is a read-only operation on priors source-of-truth — priors JSON files are
    never mutated at runtime.

    If write_back=True (explicit build-step only), also stamps the compiled block
    into each priors JSON schema.compiled. This is for audit portability and should
    only be called from scripts/emit-compiled-triggers.py, never at runtime boot.
    """
    # Ensure caches are populated
    get_matcher()

    if not os.path.isdir(PRIORS_DIR):
        return

    # Build reverse index: library_id → list of {term, matched_via, confidence}
    lib_triggers: dict[str, list[dict]] = {}
    for term, info in _motif_by_trigger.items():
        lib_id = info.get("library_id", "")
        if not lib_id:
            continue
        matched_via = info.get("matched_via", "detect")
        lib_triggers.setdefault(lib_id, []).append({
            "term": term,
            "matched_via": matched_via,
            "confidence": _DEFAULT_WEIGHTS.get(matched_via, 0.7),
        })

    # Count negative triggers per library (total individual negative patterns, not sets)
    lib_negatives: dict[str, int] = {
        lib_id: len(negs) for lib_id, negs in _negative_triggers.items()
    }

    # Collect per-file stats
    from datetime import datetime, timezone
    file_stats: dict[str, dict] = {}
    for fname in sorted(os.listdir(PRIORS_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(PRIORS_DIR, fname)
        try:
            with open(fpath) as f:
                mod = json.load(f)

            schema = mod.get("schema")
            if not schema:
                continue

            file_triggers = []
            total_phrases = 0
            total_lexemes = 0
            total_negatives = 0
            for collection_key, id_field in [
                ("motifs", "motif_id"),
                ("concepts", "concept_id"),
                ("milestones", "event_id"),
            ]:
                for entry in mod.get(collection_key, []):
                    entry_id = entry.get(id_field, "")
                    triggers = lib_triggers.get(entry_id, [])
                    file_triggers.extend(triggers)
                    for t in triggers:
                        if t["matched_via"] == "phrase":
                            total_phrases += 1
                        elif t["matched_via"] == "lexeme":
                            total_lexemes += 1
                    total_negatives += lib_negatives.get(entry_id, 0)

            compiled_block = {
                "generated_by": "pattern_cache._emit_compiled_triggers",
                "total_indexed_terms": len(file_triggers),
                "phrases": total_phrases,
                "lexemes": total_lexemes,
                "features": len(file_triggers) - total_phrases - total_lexemes,
                "negative_triggers_total": total_negatives,
            }
            file_stats[fname] = compiled_block

            # Write-back mode: stamp into priors JSON (explicit build-step only)
            if write_back:
                schema["compiled"] = compiled_block
                with open(fpath, "w") as f:
                    json.dump(mod, f, indent=2, ensure_ascii=False)
                    f.write("\n")

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to process {fname}: {e}")
            continue

    # Write combined artifact to audit-logs/compiled_triggers/latest.json
    try:
        os.makedirs(COMPILED_TRIGGERS_DIR, exist_ok=True)
        artifact = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_by": "pattern_cache._emit_compiled_triggers",
            "write_back": write_back,
            "total_terms_in_regex": len(_pattern_lookup),
            "total_structured_entries": len(_library_entries),
            "total_negative_trigger_entries": len(_negative_triggers),
            "per_file": file_stats,
        }
        artifact_path = os.path.join(COMPILED_TRIGGERS_DIR, "latest.json")
        with open(artifact_path, "w") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
            f.write("\n")
        logger.info(f"Compiled trigger artifact written to {artifact_path}")
    except OSError as e:
        logger.warning(f"Failed to write compiled trigger artifact: {e}")


def get_library_entry(library_id: str) -> dict | None:
    """Look up a full structured library entry by ID (motif_id, concept_id, event_id).

    Ensures caches are loaded first. Returns None if not found.
    """
    get_matcher()  # ensure caches are populated
    return _library_entries.get(library_id)


def get_lineage_neighbors(event_id: str) -> list[str]:
    """Get lineage edge neighbors for a milestone.

    Returns list of adjacent event_ids from the lineage graph.
    """
    get_matcher()  # ensure caches are populated
    return _lineage_graph.get(event_id, [])


def check_lineage_coherence(matched_ids: list[str]) -> dict:
    """Check whether a set of matched milestone IDs form a coherent lineage path.

    Returns:
        {
            "coherent": bool,       # True if all matched milestones are lineage-connected
            "connected_pairs": int, # Number of pairs that share a lineage edge
            "total_pairs": int,     # Total possible pairs
            "orphans": list[str],   # IDs with no lineage connection to other matched IDs
            "details": str,         # Human-readable summary
        }
    """
    get_matcher()
    milestone_ids = [mid for mid in matched_ids if mid in _lineage_graph or mid in _library_entries]
    if len(milestone_ids) < 2:
        return {
            "coherent": True,
            "connected_pairs": 0,
            "total_pairs": 0,
            "orphans": [],
            "details": f"Only {len(milestone_ids)} milestone(s) matched — coherence check requires 2+",
        }

    # Build adjacency check: for each pair, check if either references the other
    connected = 0
    total = 0
    connections: dict[str, set[str]] = {mid: set() for mid in milestone_ids}
    for i, a in enumerate(milestone_ids):
        for b in milestone_ids[i + 1:]:
            total += 1
            a_edges = set(_lineage_graph.get(a, []))
            b_edges = set(_lineage_graph.get(b, []))
            if b in a_edges or a in b_edges:
                connected += 1
                connections[a].add(b)
                connections[b].add(a)

    orphans = [mid for mid, conns in connections.items() if not conns]
    coherent = len(orphans) == 0

    return {
        "coherent": coherent,
        "connected_pairs": connected,
        "total_pairs": total,
        "orphans": orphans,
        "details": (
            f"{connected}/{total} pairs connected, "
            f"{len(orphans)} orphan(s){': ' + ', '.join(orphans) if orphans else ''}"
        ),
    }
