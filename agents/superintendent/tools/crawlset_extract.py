import os
import json
import urllib.request
import urllib.error
from python.helpers.tool import Tool, Response


CRAWLSET_URL = os.environ.get("CRAWLSET_URL", "http://host.docker.internal:8001")


class CrawlsetExtract(Tool):
    """Trigger web intelligence extractions via the Crawlset pipeline."""

    async def execute(self, action="extract", **kwargs):
        try:
            if action == "extract":
                return await self._start_extraction(**kwargs)
            elif action == "status":
                return await self._check_status(**kwargs)
            elif action == "search":
                return await self._search(**kwargs)
            elif action == "websets":
                return await self._list_websets(**kwargs)
            elif action == "create_webset":
                return await self._create_webset(**kwargs)
            elif action == "health":
                return await self._health(**kwargs)
            else:
                return Response(
                    message=f"Unknown action: {action}. Use: extract, status, search, websets, create_webset, health",
                    break_loop=False,
                )
        except urllib.error.URLError as e:
            return Response(
                message=f"Crawlset connection failed at {CRAWLSET_URL}: {e}. Start with: docker compose -f docker-compose.web-intelligence.yml up -d",
                break_loop=False,
            )
        except Exception as e:
            return Response(message=f"Crawlset error: {e}", break_loop=False)

    async def _start_extraction(self, url="", enrichments=None, queue="realtime", **kwargs):
        if not url:
            return Response(message="Provide a URL to extract.", break_loop=False)

        payload = {"url": url, "queue": queue}
        if enrichments:
            payload["enrichments"] = enrichments if isinstance(enrichments, list) else [enrichments]

        result = self._post("/api/extraction/start", payload)
        job_id = result.get("job_id", "unknown")
        return Response(
            message=f"Extraction started for {url}\njob_id: {job_id}\nCheck status with action='status', job_id='{job_id}'",
            break_loop=False,
        )

    async def _check_status(self, job_id="", **kwargs):
        if not job_id:
            return Response(message="Provide job_id to check.", break_loop=False)
        result = self._get(f"/api/extraction/{job_id}")
        return Response(
            message=f"Job {job_id}: {json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _search(self, query="", webset_id="", limit=10, **kwargs):
        if not query:
            return Response(message="Provide a search query.", break_loop=False)
        payload = {"query": query, "limit": int(limit)}
        if webset_id:
            payload["webset_id"] = webset_id
        result = self._post("/api/search", payload)
        items = result.get("results", [])
        if not items:
            return Response(message="No results found.", break_loop=False)
        text = f"Found {len(items)} results:\n\n"
        for item in items:
            text += f"- {item.get('title', 'Untitled')}\n  URL: {item.get('url', '?')}\n  Score: {item.get('score', '?')}\n\n"
        return Response(message=text, break_loop=False)

    async def _list_websets(self, **kwargs):
        result = self._get("/api/websets")
        websets = result.get("websets", result) if isinstance(result, dict) else result
        if not websets:
            return Response(message="No websets found.", break_loop=False)
        if isinstance(websets, list):
            text = "Websets:\n" + "\n".join(f"- {w.get('name', '?')} (id={w.get('id', '?')}, items={w.get('item_count', '?')})" for w in websets)
        else:
            text = f"Websets: {json.dumps(websets, indent=2)}"
        return Response(message=text, break_loop=False)

    async def _create_webset(self, name="", description="", **kwargs):
        if not name:
            return Response(message="Provide a webset name.", break_loop=False)
        payload = {"name": name}
        if description:
            payload["description"] = description
        result = self._post("/api/websets", payload)
        return Response(
            message=f"Webset created: {json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _health(self, **kwargs):
        result = self._get("/health")
        return Response(message=f"Crawlset health: {json.dumps(result)}", break_loop=False)

    def _get(self, path):
        req = urllib.request.Request(f"{CRAWLSET_URL}{path}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def _post(self, path, data):
        body = json.dumps(data).encode()
        req = urllib.request.Request(f"{CRAWLSET_URL}{path}", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
