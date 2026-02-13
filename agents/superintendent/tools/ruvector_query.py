import os
import json
import urllib.request
import urllib.error
from python.helpers.tool import Tool, Response


RUVECTOR_URL = os.environ.get("RUVECTOR_URL", "http://host.docker.internal:6334")


class RuVectorQuery(Tool):
    """Query the RuVector HNSW+GNN vector database."""

    async def execute(self, action="search", collection="mogul_memory", **kwargs):
        try:
            if action == "search":
                return await self._search(collection, **kwargs)
            elif action == "insert":
                return await self._insert(collection, **kwargs)
            elif action == "collections":
                return await self._list_collections(**kwargs)
            elif action == "stats":
                return await self._stats(**kwargs)
            elif action == "graph_query":
                return await self._graph_query(**kwargs)
            elif action == "health":
                return await self._health(**kwargs)
            else:
                return Response(
                    message=f"Unknown action: {action}. Use: search, insert, collections, stats, graph_query, health",
                    break_loop=False,
                )
        except urllib.error.URLError as e:
            return Response(
                message=f"RuVector connection failed at {RUVECTOR_URL}: {e}. Is the web-intelligence stack running? Start with: docker compose -f docker-compose.web-intelligence.yml up -d",
                break_loop=False,
            )
        except Exception as e:
            return Response(message=f"RuVector error: {e}", break_loop=False)

    async def _search(self, collection, query="", embedding=None, top_k=10, filter_metadata=None, **kwargs):
        if not query and not embedding:
            return Response(message="Provide query text or embedding vector.", break_loop=False)

        # If we have query text but no embedding, generate one
        if query and not embedding:
            from python.helpers.memory import Memory
            db = await Memory.get(self.agent)
            embedding = list(db.db.embedding_function.embed_query(query))

        payload = {
            "embedding": embedding,
            "top_k": int(top_k),
            "collection": collection,
        }
        if filter_metadata:
            payload["filter_metadata"] = filter_metadata if isinstance(filter_metadata, dict) else json.loads(filter_metadata)

        result = self._post("/search", payload)
        results = result.get("results", [])
        if not results:
            return Response(message=f"No results found in collection '{collection}'.", break_loop=False)

        text = f"Found {len(results)} results in '{collection}':\n\n"
        for r in results:
            text += f"- [{r.get('id', '?')}] score={r.get('score', 0):.4f}: {r.get('text', '')[:200]}\n"
            if r.get("metadata"):
                text += f"  metadata: {json.dumps(r['metadata'])}\n"
        return Response(message=text, break_loop=False)

    async def _insert(self, collection, text="", metadata=None, doc_id=None, **kwargs):
        if not text:
            return Response(message="Provide text to insert.", break_loop=False)

        from python.helpers.memory import Memory
        db = await Memory.get(self.agent)
        embedding = list(db.db.embedding_function.embed_query(text))

        payload = {
            "text": text,
            "embedding": embedding,
            "collection": collection,
        }
        if doc_id:
            payload["id"] = doc_id
        if metadata:
            payload["metadata"] = metadata if isinstance(metadata, dict) else json.loads(metadata)

        result = self._post("/documents", payload)
        return Response(
            message=f"Inserted into '{collection}': id={result.get('id', 'unknown')}",
            break_loop=False,
        )

    async def _list_collections(self, **kwargs):
        result = self._get("/collections")
        collections = result.get("collections", [])
        if not collections:
            return Response(message="No collections found.", break_loop=False)
        text = "Collections:\n" + "\n".join(f"- {c.get('name', '?')} (dim={c.get('dimension', '?')}, docs={c.get('document_count', '?')})" for c in collections)
        return Response(message=text, break_loop=False)

    async def _stats(self, **kwargs):
        result = self._get("/stats")
        return Response(message=f"RuVector stats:\n{json.dumps(result, indent=2)}", break_loop=False)

    async def _graph_query(self, query_text="", **kwargs):
        if not query_text:
            return Response(message="Provide query_text for graph query.", break_loop=False)
        result = self._post("/graph/query", {"query": query_text})
        return Response(message=f"Graph query result:\n{json.dumps(result, indent=2)}", break_loop=False)

    async def _health(self, **kwargs):
        result = self._get("/health")
        return Response(message=f"RuVector health: {json.dumps(result)}", break_loop=False)

    def _get(self, path):
        req = urllib.request.Request(f"{RUVECTOR_URL}{path}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def _post(self, path, data):
        body = json.dumps(data).encode()
        req = urllib.request.Request(f"{RUVECTOR_URL}{path}", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
