from __future__ import annotations

import asyncio
import os
import pickle
from pyee import AsyncIOEventEmitter
from nats.aio.client import Client as NATS


class AsyncEventBus(AsyncIOEventEmitter):
    """Singleton event bus backed by NATS for scalable messaging."""

    _instance: "AsyncEventBus" | None = None

    def __init__(self) -> None:
        super().__init__(loop=asyncio.get_event_loop())
        self._nats = NATS()
        self._nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        self._nats_connected = False
        # connect in background so first emit won't block
        asyncio.create_task(self._connect_nats())

    @classmethod
    def get(cls) -> "AsyncEventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _connect_nats(self):
        if self._nats_connected:
            return
        try:
            await self._nats.connect(self._nats_url)
            await self._nats.subscribe("a0.events.*", cb=self._on_nats)
            self._nats_connected = True
        except Exception:
            # fail silently and fall back to in-process events
            self._nats_connected = False

    async def _on_nats(self, msg):
        event = msg.subject.split(".")[-1]
        try:
            payload = pickle.loads(msg.data)
        except Exception:
            payload = {"args": [], "kwargs": {}}
        super().emit(event, *payload.get("args", []), **payload.get("kwargs", {}))

    def emit(self, event: str, *args, **kwargs):
        handled = super().emit(event, *args, **kwargs)
        if self._nats_connected:
            try:
                data = pickle.dumps({"args": args, "kwargs": kwargs})
                asyncio.create_task(self._nats.publish(f"a0.events.{event}", data))
            except Exception:
                pass
        return handled
