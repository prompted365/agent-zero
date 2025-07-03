import os
import sys
import threading
from typing import Generator

# Ensure project root is on sys.path for tests
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pytest
from flask import Flask

from agent import AgentContext, AgentConfig, ModelConfig
import models


@pytest.fixture
def agent_config() -> AgentConfig:
    """Provide a minimal AgentConfig for tests."""

    dummy_model = ModelConfig(
        provider=models.ModelProvider.OLLAMA,
        name="tiny",
    )
    return AgentConfig(
        chat_model=dummy_model,
        utility_model=dummy_model,
        embeddings_model=dummy_model,
        browser_model=dummy_model,
        mcp_servers="{}",
    )


@pytest.fixture
def agent_context(agent_config: AgentConfig) -> Generator[AgentContext, None, None]:
    """Create and clean up an AgentContext for a test."""

    ctx = AgentContext(config=agent_config)
    try:
        yield ctx
    finally:
        AgentContext.remove(ctx.id)


@pytest.fixture
def flask_app() -> Flask:
    """Instantiate a minimal Flask app for API handlers."""

    app = Flask(__name__)
    return app


@pytest.fixture
def health_handler(flask_app: Flask) -> "HealthCheck":
    """Return a HealthCheck API handler instance."""

    from python.api.health import HealthCheck

    return HealthCheck(flask_app, threading.Lock())


@pytest.fixture
def event_bus(monkeypatch) -> Generator:
    """Yield an AsyncEventBus instance with NATS disabled."""

    from python.helpers import event_bus as event_bus_module

    class DummyNATS:
        published = []

        async def connect(self, url):
            return None

        async def subscribe(self, *args, **kwargs):
            return None

        async def publish(self, subject, data):
            self.published.append((subject, data))

    def dummy_init(self):
        import asyncio as _asyncio
        event_bus_module.AsyncIOEventEmitter.__init__(self, loop=_asyncio.get_event_loop())
        self._nats = DummyNATS()
        self._nats_url = "nats://localhost:4222"
        self._nats_connected = False

    monkeypatch.setattr(event_bus_module, "NATS", DummyNATS)
    monkeypatch.setattr(event_bus_module.AsyncEventBus, "__init__", dummy_init)

    event_bus_module.AsyncEventBus._instance = None
    bus = event_bus_module.AsyncEventBus.get()

    yield bus

    event_bus_module.AsyncEventBus._instance = None
