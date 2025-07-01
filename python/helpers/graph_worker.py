import asyncio
import networkx as nx

from python.helpers.event_bus import AsyncEventBus


class KnowledgeGraphWorker:
    """Cyclical worker maintaining a runtime knowledge graph."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self.bus = AsyncEventBus.get()
        # subscribe to bus events
        self.bus.on("user.message", lambda msg: asyncio.create_task(self._add_user(msg)))
        self.bus.on("agent.message", lambda msg: asyncio.create_task(self._add_agent(msg)))
        self.bus.on("agent.intent", lambda msg: asyncio.create_task(self._add_intent(msg)))
        self.bus.on("agent.thought", lambda msg: asyncio.create_task(self._add_thought(msg)))

    async def _add_user(self, msg):
        self.graph.add_node(self.graph.number_of_nodes(), type="user", text=getattr(msg, "message", str(msg)))

    async def _add_agent(self, msg):
        self.graph.add_node(self.graph.number_of_nodes(), type="agent", text=str(msg))

    async def _add_intent(self, msg):
        self.graph.add_node(self.graph.number_of_nodes(), type="intent", text=str(msg))

    async def _add_thought(self, msg):
        self.graph.add_node(self.graph.number_of_nodes(), type="thought", text=str(msg))

    def export(self):
        return nx.node_link_data(self.graph)
