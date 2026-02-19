"""
Bicameral Model Orchestrator — Router + Load Balancer for Mogul

Fires at util_model_call_before (before every utility model call).
Routes calls to one of two backend models using least-pending-normalized
selection: score = pending_count * ema_latency_ms, pick the lower lane.

Transparent: when BICAM_ENABLED=false, all calls proceed with the
default utility model. Existing extensions are unmodified.

Architecture:
  call_utility_model()
        |
  [util_model_call_before]
        |
  _10_bicameral_router
   1. Fingerprint caller (regex on system prompt) → lane A/B/meta
   2. Dedup check (hash-based, zero overhead)
   3. Lane score comparison → pick least loaded
   4. Replace call_data["model"] with lane model
   5. Inject context surface projection into call_data["system"]

Note: _router_model (Gemma 3 via Ollama) is still constructed at init
for future workflow use, but is NOT in the routing hot path.
"""

import hashlib
import os
import re
import sys
import time
from collections import deque

from python.helpers.extension import Extension

# Add extensions dir to path for _helpers import
_ext_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ext_dir not in sys.path:
    sys.path.insert(0, _ext_dir)

from _helpers.router_config import (
    load_config,
    BicameralConfig,
    LANE_A_PATTERNS,
    LANE_B_PATTERNS,
    META_PATTERNS,
)
from _helpers.context_surface import ContextSurface

# --- Module-level singletons (constructed once per process) ---

_config: BicameralConfig | None = None
_model_a = None
_model_b = None
_router_model = None
_surface: ContextSurface | None = None
_recent_hashes: deque = deque(maxlen=20)  # for dedup detection
_initialized = False

# Pre-compiled regex patterns for lane assignment
_lane_a_re = None
_lane_b_re = None
_meta_re = None
_round_robin_counter = 0


def _init_models(agent):
    """Lazy-initialize models and config on first call."""
    global _config, _model_a, _model_b, _router_model, _surface
    global _initialized, _lane_a_re, _lane_b_re, _meta_re

    if _initialized:
        return

    _config = load_config()

    if not _config.enabled:
        _initialized = True
        return

    # Import here to avoid circular imports at module load
    from models import get_chat_model, ModelConfig, ModelType

    # Construct lane models
    a_kwargs = {}
    if _config.model_a.api_key:
        a_kwargs["api_key"] = _config.model_a.api_key
    if _config.model_a.api_base:
        a_kwargs["api_base"] = _config.model_a.api_base

    _model_a = get_chat_model(
        provider=_config.model_a.provider,
        name=_config.model_a.name,
        **a_kwargs,
    )

    b_kwargs = {}
    if _config.model_b.api_key:
        b_kwargs["api_key"] = _config.model_b.api_key
    if _config.model_b.api_base:
        b_kwargs["api_base"] = _config.model_b.api_base

    _model_b = get_chat_model(
        provider=_config.model_b.provider,
        name=_config.model_b.name,
        **b_kwargs,
    )

    # Construct router model (Gemma 3 via Ollama)
    _router_model = get_chat_model(
        provider=_config.router.provider,
        name=_config.router.name,
        api_base=_config.router.api_base,
    )

    # Init context surface singleton
    _surface = ContextSurface()

    # Compile lane regex patterns
    _lane_a_re = re.compile("|".join(LANE_A_PATTERNS), re.IGNORECASE)
    _lane_b_re = re.compile("|".join(LANE_B_PATTERNS), re.IGNORECASE)
    _meta_re = re.compile("|".join(META_PATTERNS), re.IGNORECASE)

    _initialized = True

    agent.context.log.log(
        type="info",
        heading="Bicameral router initialized",
        content=(
            f"Lane A: {_config.model_a.provider}/{_config.model_a.name}\n"
            f"Lane B: {_config.model_b.provider}/{_config.model_b.name}\n"
            f"Router: {_config.router.provider}/{_config.router.name}"
        ),
    )


class NoOpModel:
    """
    Returns empty response immediately. Used for circuit-breaker skip.
    Extensions already handle empty responses gracefully (they all check
    `if not result`).
    """

    async def unified_call(self, **kwargs):
        return "", ""


def _fingerprint_lane(system_prompt: str) -> tuple[str, str]:
    """
    Deterministic lane assignment based on system prompt content.
    Returns (lane, category) where lane is "A", "B", or "meta".
    """
    if _lane_a_re and _lane_a_re.search(system_prompt):
        match = _lane_a_re.search(system_prompt)
        return "A", match.group(0) if match else "faiss"

    if _lane_b_re and _lane_b_re.search(system_prompt):
        match = _lane_b_re.search(system_prompt)
        return "B", match.group(0) if match else "ruvector"

    if _meta_re and _meta_re.search(system_prompt):
        return "meta", "validation"

    return "round_robin", "unknown"


def _request_hash(system: str, message: str) -> str:
    """Fast hash for dedup detection."""
    combined = f"{system[:200]}|{message[:200]}"
    return hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()[:12]


def _is_duplicate(req_hash: str) -> bool:
    """Check if this request hash was seen recently."""
    if req_hash in _recent_hashes:
        return True
    _recent_hashes.append(req_hash)
    return False


class BicameralRouter(Extension):
    __version__ = "1.0.0"
    __requires_a0__ = ">=0.8"
    __schema__ = "call_data[model,system] (write)"

    async def execute(self, call_data: dict = {}, **kwargs):
        # Lazy init on first call
        _init_models(self.agent)

        if not _config or not _config.enabled:
            return  # Transparent bypass — default model proceeds

        system = call_data.get("system", "")
        message = call_data.get("message", "")

        # 1. Fingerprint caller (kept for logging/observability)
        lane, category = _fingerprint_lane(system)
        fingerprinted_lane = lane

        # 2. Dedup check (zero overhead, hash-based)
        req_hash = _request_hash(system, message)
        is_dup = _is_duplicate(req_hash)
        if is_dup:
            _surface.record_skip()
            call_data["model"] = NoOpModel()
            self.agent.context.log.log(
                type="util",
                heading=f"Bicameral: SKIP ({category}, dup=True)",
                content=f"hash={req_hash}",
            )
            return

        # 3. Least-pending-normalized lane selection
        #    score = pending_count * ema_latency_ms — lower is less loaded
        score_a = _surface.get_lane_score("A")
        score_b = _surface.get_lane_score("B")

        if lane in ("meta", "round_robin"):
            # No fingerprint affinity — pure load-based selection
            lane = "A" if score_a <= score_b else "B"
            global _round_robin_counter
            if category == "unknown":
                _round_robin_counter += 1
                category = f"rr_{_round_robin_counter}"
        else:
            # Fingerprinted lane, but redirect if significantly more loaded
            if lane == "A" and score_a > score_b * 2 and score_b > 0:
                lane = "B"
            elif lane == "B" and score_b > score_a * 2 and score_a > 0:
                lane = "A"

        # 4. Replace model with lane model
        if lane == "A":
            call_data["model"] = _model_a
        else:
            call_data["model"] = _model_b

        # 5. Inject context surface projection into system prompt
        projection = _surface.get_projection()
        call_data["system"] = f"{projection}\n{system}"

        # 6. Update surface state (pending++)
        _surface.begin_call(lane, category)

        # 7. Record timing via a wrapper that decrements pending on completion
        original_model = call_data["model"]
        call_start = time.monotonic()
        call_lane = lane

        class TimingWrapper:
            """Wraps a model to record call timing on the context surface."""

            def __init__(self, inner, start_time, tracked_lane):
                self._inner = inner
                self._start = start_time
                self._lane = tracked_lane

            def __getattr__(self, name):
                return getattr(self._inner, name)

            async def unified_call(self, **kw):
                try:
                    result = await self._inner.unified_call(**kw)
                    return result
                finally:
                    elapsed_ms = int((time.monotonic() - self._start) * 1000)
                    _surface.end_call(self._lane, elapsed_ms)

        call_data["model"] = TimingWrapper(original_model, call_start, call_lane)

        redirected = fingerprinted_lane != call_lane
        redirect_str = f" -> lane_{call_lane} (REDIRECT)" if redirected else ""

        self.agent.context.log.log(
            type="util",
            heading=f"Bicameral: lane_{call_lane} ({category}) scores=A:{score_a:.0f}/B:{score_b:.0f}",
            content=(
                f"fingerprint=lane_{fingerprinted_lane}{redirect_str}\n"
                f"A: pending={_surface.get_pending('A')} ema={_surface._lane_a_ema_ms:.0f}ms score={score_a:.1f}\n"
                f"B: pending={_surface.get_pending('B')} ema={_surface._lane_b_ema_ms:.0f}ms score={score_b:.1f}\n"
                f"{projection}"
            ),
        )

        # 8. Update active context from extras_persistent if available
        try:
            loop_data = getattr(self.agent, "loop_data", None)
            if loop_data:
                extras = getattr(loop_data, "extras_persistent", {})
                drift_data = extras.get("quiver_drift_data", {})
                chorus_data = extras.get("ghost_chorus_meta", {})
                _surface.update_active_context(
                    drift_band=drift_data.get("drift_band", ""),
                    chorus_mode=chorus_data.get("mode", ""),
                    topic_novelty=drift_data.get("topic_novelty", 0.0),
                )
        except Exception:
            pass  # Context enrichment is best-effort
