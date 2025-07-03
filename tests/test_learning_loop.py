import asyncio
import sys
import types

# Provide dummy pyee and event bus to avoid external deps

dummy_pyee = types.ModuleType('pyee')
class _DummyEmitter:
    def __init__(self, *a, **k):
        pass
sys.modules.setdefault('pyee', dummy_pyee)
dummy_pyee.AsyncIOEventEmitter = _DummyEmitter

class _DummyEventBus:
    _instance = None
    def __init__(self):
        self._listeners = {}
    @classmethod
    def get(cls):
        cls._instance = cls._instance or cls()
        return cls._instance
    def on(self, event, cb):
        self._listeners.setdefault(event, []).append(cb)
    def emit(self, event, *a, **k):
        for cb in self._listeners.get(event, []):
            cb(*a, **k)

dummy_event_bus = types.ModuleType('python.helpers.event_bus')
dummy_event_bus.AsyncEventBus = _DummyEventBus
sys.modules['python.helpers.event_bus'] = dummy_event_bus

from python.helpers.event_bus import AsyncEventBus
from python.helpers.learning_loop import LearningLoop


def test_learning_loop_collects_logs():
    loop = LearningLoop(max_records=2)
    loop.start()
    bus = AsyncEventBus.get()
    bus.emit("log.record", {"type": "info", "heading": "h1", "content": "c1"})
    bus.emit("log.record", {"type": "warning", "heading": "h2", "content": "c2"})
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))
    retro = loop.summarize_retro()
    projected = loop.summarize_projected()
    assert "h1" in retro and "h2" in retro
    assert "Monitor issue" in projected
    loop.stop()
