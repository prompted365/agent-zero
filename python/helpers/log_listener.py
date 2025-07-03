import asyncio
import json
import os

from python.helpers.event_bus import AsyncEventBus


class StructuredLogListener:
    """Default listener that writes log events to a JSONL file."""

    def __init__(self, logfile: str = "logs/events.jsonl") -> None:
        self.logfile = logfile
        os.makedirs(os.path.dirname(self.logfile), exist_ok=True)
        self._lock = asyncio.Lock()
        bus = AsyncEventBus.get()
        bus.on("log.record", lambda record: asyncio.create_task(self._write(record)))

    async def _write(self, record: dict) -> None:
        async with self._lock:
            try:
                with open(self.logfile, "a", encoding="utf-8") as f:
                    json.dump(record, f)
                    f.write("\n")
            except Exception:
                pass
