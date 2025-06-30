import asyncio
from pyee import AsyncIOEventEmitter


class AsyncEventBus(AsyncIOEventEmitter):
    """Singleton event bus based on AsyncIOEventEmitter."""

    _instance: "AsyncEventBus" | None = None

    def __init__(self) -> None:
        super().__init__(loop=asyncio.get_event_loop())

    @classmethod
    def get(cls) -> "AsyncEventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
