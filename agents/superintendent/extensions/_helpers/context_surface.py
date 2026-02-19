"""
Bicameral Context Surface — shared in-memory state projected across both model lanes.

Thread-safe singleton tracking call frequencies, lane loads, and circuit breaker state.
Compressed to a single-line prefix injected into every utility model system prompt,
giving both models cross-lane awareness without direct communication.

Ephemeral working state only — no persistence needed.
"""

import threading
import time
from collections import deque


# Rolling window size in seconds for frequency counters
_WINDOW_SECONDS = 60.0


class ContextSurface:
    """Thread-safe singleton tracking bicameral router state."""

    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._lock = threading.Lock()
                    inst._tick = 0
                    inst._lane_a_pending = 0
                    inst._lane_b_pending = 0
                    inst._lane_a_last_category = ""
                    inst._lane_b_last_category = ""
                    inst._lane_a_last_latency_ms = 0
                    inst._lane_b_last_latency_ms = 0
                    inst._skip_count = 0
                    inst._defer_count = 0
                    inst._tripped = False
                    # EMA latency tracking (ms) — seeded at observed Gemini Flash median
                    inst._lane_a_ema_ms = 1200.0
                    inst._lane_b_ema_ms = 1200.0
                    inst._EMA_ALPHA = 0.3
                    # Rolling window deques: (timestamp,) entries
                    inst._faiss_calls = deque()
                    inst._ruvector_calls = deque()
                    inst._meta_calls = deque()
                    inst._skipped_calls = deque()
                    inst._deferred_calls = deque()
                    # Active context from extras_persistent
                    inst._drift_band = "unknown"
                    inst._chorus_mode = "unknown"
                    inst._topic_novelty = 0.0
                    cls._instance = inst
        return cls._instance

    def _prune_window(self, dq: deque, now: float) -> int:
        """Remove entries older than the rolling window and return count."""
        cutoff = now - _WINDOW_SECONDS
        while dq and dq[0] < cutoff:
            dq.popleft()
        return len(dq)

    def begin_call(self, lane: str, category: str) -> None:
        """Record that a call is starting on the given lane."""
        now = time.monotonic()
        with self._lock:
            self._tick += 1
            if lane == "A":
                self._lane_a_pending += 1
                self._lane_a_last_category = category
                self._faiss_calls.append(now)
            elif lane == "B":
                self._lane_b_pending += 1
                self._lane_b_last_category = category
                self._ruvector_calls.append(now)
            else:
                self._meta_calls.append(now)

    def end_call(self, lane: str, latency_ms: int) -> None:
        """Record that a call has completed on the given lane, updating EMA."""
        with self._lock:
            alpha = self._EMA_ALPHA
            if lane == "A":
                self._lane_a_pending = max(0, self._lane_a_pending - 1)
                self._lane_a_last_latency_ms = latency_ms
                self._lane_a_ema_ms = alpha * latency_ms + (1 - alpha) * self._lane_a_ema_ms
            elif lane == "B":
                self._lane_b_pending = max(0, self._lane_b_pending - 1)
                self._lane_b_last_latency_ms = latency_ms
                self._lane_b_ema_ms = alpha * latency_ms + (1 - alpha) * self._lane_b_ema_ms

    def record_skip(self) -> None:
        """Record a circuit-breaker skip."""
        now = time.monotonic()
        with self._lock:
            self._skip_count += 1
            self._skipped_calls.append(now)

    def record_defer(self) -> None:
        """Record a circuit-breaker defer."""
        now = time.monotonic()
        with self._lock:
            self._defer_count += 1
            self._deferred_calls.append(now)
            # Trip the circuit breaker when deferring
            self._tripped = True

    def update_active_context(
        self,
        drift_band: str = "",
        chorus_mode: str = "",
        topic_novelty: float = 0.0,
    ) -> None:
        """Update shared context from extras_persistent."""
        with self._lock:
            if drift_band:
                self._drift_band = drift_band
            if chorus_mode:
                self._chorus_mode = chorus_mode
            if topic_novelty > 0:
                self._topic_novelty = topic_novelty

    def get_pending(self, lane: str) -> int:
        """Get pending call count for a lane."""
        with self._lock:
            if lane == "A":
                return self._lane_a_pending
            elif lane == "B":
                return self._lane_b_pending
            return 0

    def get_lane_score(self, lane: str) -> float:
        """Return (pending_count + epsilon) * ema_latency_ms. Lower = less loaded.
        Epsilon (0.01) ensures 0-pending lanes still differentiate by EMA speed."""
        with self._lock:
            if lane == "A":
                return (self._lane_a_pending + 0.01) * self._lane_a_ema_ms
            elif lane == "B":
                return (self._lane_b_pending + 0.01) * self._lane_b_ema_ms
            return 0.0

    def get_state(self) -> dict:
        """Get full state snapshot (for logging/debugging)."""
        now = time.monotonic()
        with self._lock:
            return {
                "tick": self._tick,
                "frequency": {
                    "faiss_lane": self._prune_window(self._faiss_calls, now),
                    "ruvector_lane": self._prune_window(self._ruvector_calls, now),
                    "meta_lane": self._prune_window(self._meta_calls, now),
                    "skipped": self._prune_window(self._skipped_calls, now),
                    "deferred": self._prune_window(self._deferred_calls, now),
                },
                "lane_a": {
                    "pending": self._lane_a_pending,
                    "last_category": self._lane_a_last_category,
                    "last_latency_ms": self._lane_a_last_latency_ms,
                },
                "lane_b": {
                    "pending": self._lane_b_pending,
                    "last_category": self._lane_b_last_category,
                    "last_latency_ms": self._lane_b_last_latency_ms,
                },
                "circuit_breaker": {
                    "tripped": self._tripped,
                    "skip_count": self._skip_count,
                    "defer_count": self._defer_count,
                },
                "active_context": {
                    "drift_band": self._drift_band,
                    "chorus_mode": self._chorus_mode,
                    "topic_novelty": self._topic_novelty,
                },
            }

    def get_projection(self) -> str:
        """
        Compressed single-line state for system prompt injection.

        Format: [BICAM: tick=42 drift=medium chorus=novel A:1pending B:2pending skip:3 freq:F12/R8/M5]
        """
        now = time.monotonic()
        with self._lock:
            f_count = self._prune_window(self._faiss_calls, now)
            r_count = self._prune_window(self._ruvector_calls, now)
            m_count = self._prune_window(self._meta_calls, now)
            s_count = self._prune_window(self._skipped_calls, now)

            return (
                f"[BICAM: tick={self._tick} "
                f"drift={self._drift_band} "
                f"chorus={self._chorus_mode} "
                f"A:{self._lane_a_pending}pending "
                f"B:{self._lane_b_pending}pending "
                f"emaA:{self._lane_a_ema_ms:.0f}/emaB:{self._lane_b_ema_ms:.0f} "
                f"skip:{s_count} "
                f"freq:F{f_count}/R{r_count}/M{m_count}]"
            )

    def reset_circuit_breaker(self) -> None:
        """Reset the tripped state (e.g., after load subsides)."""
        with self._lock:
            self._tripped = False
