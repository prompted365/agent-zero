import asyncio
import pickle
import sys
import types

import pyee.asyncio

# Expose AsyncIOEventEmitter at top-level "pyee" module for compatibility
if 'pyee' not in sys.modules:
    dummy_pyee = types.ModuleType('pyee')
    sys.modules['pyee'] = dummy_pyee
else:
    dummy_pyee = sys.modules['pyee']

dummy_pyee.AsyncIOEventEmitter = pyee.asyncio.AsyncIOEventEmitter

from python.helpers.event_bus import AsyncEventBus


def test_event_bus_emit_and_listener(event_bus):
    results = []

    async def listener(val):
        results.append(val)

    event_bus.on("test", listener)
    handled = event_bus.emit("test", 123)

    # allow scheduled callbacks to run
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))

    assert handled is True
    assert results == [123]


def test_event_bus_emit_returns_false(event_bus):
    handled = event_bus.emit("unhandled", 1)
    assert handled is False


def test_event_bus_on_nats(event_bus):
    captured = []
    event_bus.on("ping", lambda x: captured.append(x))

    payload = pickle.dumps({"args": ["pong"], "kwargs": {}})

    class Msg:
        def __init__(self, data):
            self.subject = "a0.events.ping"
            self.data = data

    asyncio.get_event_loop().run_until_complete(event_bus._on_nats(Msg(payload)))

    assert captured == ["pong"]
