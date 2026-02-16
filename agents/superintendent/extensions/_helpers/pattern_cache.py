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
from typing import NamedTuple

PRIORS_DIR = os.environ.get(
    "PRIORS_MODULE_DIR",
    "/workspace/operationTorque/compliance-modules/priors",
)

class PatternAnchor(NamedTuple):
    term: str
    module_id: str
    domain: str


# Module-level cache
_compiled_pattern: re.Pattern | None = None
_pattern_lookup: dict[str, PatternAnchor] = {}


def _load_modules() -> list[PatternAnchor]:
    """Walk priors directory and extract all detect-tier patterns."""
    anchors = []
    if not os.path.isdir(PRIORS_DIR):
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
        except (json.JSONDecodeError, OSError):
            continue
    return anchors


def get_matcher() -> tuple[re.Pattern | None, dict[str, PatternAnchor]]:
    """Return compiled regex and lookup dict. Cached after first call."""
    global _compiled_pattern, _pattern_lookup
    if _compiled_pattern is not None:
        return _compiled_pattern, _pattern_lookup

    anchors = _load_modules()
    if not anchors:
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
            results.append({
                "term": anchor.term,
                "module_id": anchor.module_id,
                "domain": anchor.domain,
                "position": match.start(),
            })
    return results
