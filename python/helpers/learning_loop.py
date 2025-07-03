from __future__ import annotations
import asyncio
from collections import deque
from typing import Deque, Dict, Any

from python.helpers.event_bus import AsyncEventBus


class LearningLoop:
    """Listen to log events and provide summarized thoughts."""

    def __init__(self, max_records: int = 50) -> None:
        self.records: Deque[Dict[str, Any]] = deque(maxlen=max_records)
        self.bus = AsyncEventBus.get()
        self._started = False

    def start(self) -> None:
        if not self._started:
            self.bus.on("log.record", self._on_log)
            self._started = True

    def stop(self) -> None:
        if self._started:
            try:
                self.bus.remove_listener("log.record", self._on_log)
            except Exception:
                pass
            self._started = False

    def _on_log(self, record: Dict[str, Any]) -> None:
        self.records.append(record)

    def summarize_retro(self, limit: int = 5) -> str:
        items = list(self.records)[-limit:]
        lines = [f"- {r.get('heading','')} {r.get('content','')}".strip() for r in items]
        return "\n".join(lines)

    def summarize_projected(self) -> str:
        # naive projection: emphasize recent warnings/errors
        projections = []
        for r in reversed(self.records):
            if r.get("type") in ("error", "warning"):
                projections.append(f"- Monitor issue: {r.get('content','').strip()}")
            if len(projections) >= 3:
                break
        return "\n".join(projections)
