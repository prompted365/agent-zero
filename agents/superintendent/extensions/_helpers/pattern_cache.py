"""
Pattern Cache — Shared helper for priors pattern matching.

Loads Detect-tier patterns from compliance-modules/priors/ JSON files,
compiles a single regex alternation for efficient matching, and caches
the compiled matcher for reuse within the process lifetime.

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


def get_matcher() -> tuple[re.Pattern | None, dict[str, PatternAnchor]]:
    """Return compiled regex and lookup dict. Cached after first call."""
    global _compiled_pattern, _pattern_lookup, _shape_term_map
    if _compiled_pattern is not None:
        return _compiled_pattern, _pattern_lookup

    anchors = _load_modules()
    _shape_term_map = _load_shape_map()

    if not anchors:
        logger.warning(f"No pattern anchors loaded from {PRIORS_DIR}")
        return None, {}

    _pattern_lookup = {a.term: a for a in anchors}
    # Sort by length descending so longer patterns match first
    terms = sorted(_pattern_lookup.keys(), key=len, reverse=True)
    escaped = [re.escape(t) for t in terms]
    _compiled_pattern = re.compile("|".join(escaped), re.IGNORECASE)
    return _compiled_pattern, _pattern_lookup


def scan_text(text: str) -> list[dict]:
    """Scan text for priors pattern anchors. Returns list of match dicts."""
    pattern, lookup = get_matcher()
    if pattern is None:
        return []

    seen = set()
    results = []
    for match in pattern.finditer(text.lower()):
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
            results.append(entry)
    return results
