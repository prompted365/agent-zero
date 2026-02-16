import os
import json
import time
import urllib.request
import urllib.error
from python.helpers.tool import Tool, Response


CRAWLSET_URL = os.environ.get("CRAWLSET_URL", "http://host.docker.internal:8001")


class CrawlsetExtract(Tool):
    """Trigger web intelligence operations via the Crawlset pipeline."""

    async def execute(self, action="extract", **kwargs):
        try:
            # Core
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
            # Monitors
            elif action == "monitors_list":
                return await self._monitors_list(**kwargs)
            elif action == "monitors_create":
                return await self._monitors_create(**kwargs)
            elif action == "monitors_get":
                return await self._monitors_get(**kwargs)
            elif action == "monitors_update":
                return await self._monitors_update(**kwargs)
            elif action == "monitors_delete":
                return await self._monitors_delete(**kwargs)
            elif action == "monitors_trigger":
                return await self._monitors_trigger(**kwargs)
            elif action == "monitors_runs":
                return await self._monitors_runs(**kwargs)
            # Analytics
            elif action == "analytics_dashboard":
                return await self._analytics_dashboard(**kwargs)
            elif action == "analytics_insights":
                return await self._analytics_insights(**kwargs)
            elif action == "analytics_trending":
                return await self._analytics_trending(**kwargs)
            elif action == "analytics_timeline":
                return await self._analytics_timeline(**kwargs)
            # Enrichments
            elif action == "enrich_item":
                return await self._enrich_item(**kwargs)
            elif action == "enrich_batch":
                return await self._enrich_batch(**kwargs)
            elif action == "enrich_webset":
                return await self._enrich_webset(**kwargs)
            elif action == "plugins_list":
                return await self._plugins_list(**kwargs)
            # Extraction (additional)
            elif action == "extract_batch":
                return await self._extract_batch(**kwargs)
            elif action == "extract_jobs":
                return await self._extract_jobs(**kwargs)
            elif action == "extract_result":
                return await self._extract_result(**kwargs)
            # Webset Items
            elif action == "webset_items":
                return await self._webset_items(**kwargs)
            elif action == "webset_add_item":
                return await self._webset_add_item(**kwargs)
            elif action == "webset_delete_item":
                return await self._webset_delete_item(**kwargs)
            elif action == "webset_stats":
                return await self._webset_stats(**kwargs)
            elif action == "webset_search":
                return await self._webset_search(**kwargs)
            # Export
            elif action == "export_json":
                return await self._export(**kwargs, fmt="json")
            elif action == "export_csv":
                return await self._export(**kwargs, fmt="csv")
            elif action == "export_markdown":
                return await self._export(**kwargs, fmt="markdown")
            else:
                return Response(
                    message=f"Unknown action: {action}. Available: extract, status, search, websets, create_webset, health, monitors_list, monitors_create, monitors_get, monitors_update, monitors_delete, monitors_trigger, monitors_runs, analytics_dashboard, analytics_insights, analytics_trending, analytics_timeline, enrich_item, enrich_batch, enrich_webset, plugins_list, extract_batch, extract_jobs, extract_result, webset_items, webset_add_item, webset_delete_item, webset_stats, webset_search, export_json, export_csv, export_markdown",
                    break_loop=False,
                )
        except urllib.error.URLError as e:
            return Response(
                message=f"Crawlset connection failed at {CRAWLSET_URL}: {e}. Start with: docker compose -f docker-compose.web-intelligence.yml up -d",
                break_loop=False,
            )
        except Exception as e:
            return Response(message=f"Crawlset error: {e}", break_loop=False)

    # ── Core ────────────────────────────────────────────────────────────

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

    # ── Monitors ──────────────────────────────────────────────────────

    async def _monitors_list(self, **kwargs):
        result = self._get("/api/monitors")
        monitors = result.get("monitors", result) if isinstance(result, dict) else result
        if not monitors:
            return Response(message="No monitors configured.", break_loop=False)
        if isinstance(monitors, list):
            text = f"Monitors ({len(monitors)}):\n"
            for m in monitors:
                text += f"- {m.get('name', '?')} (id={m.get('id', '?')}, schedule={m.get('schedule', '?')}, url={m.get('url', '?')})\n"
        else:
            text = f"Monitors: {json.dumps(monitors, indent=2)}"
        return Response(message=text, break_loop=False)

    async def _monitors_create(self, name="", url="", schedule="", enrichments=None, **kwargs):
        if not name or not url:
            return Response(message="Provide name and url to create a monitor.", break_loop=False)
        payload = {"name": name, "url": url}
        if schedule:
            payload["schedule"] = schedule
        if enrichments:
            payload["enrichments"] = enrichments if isinstance(enrichments, list) else [enrichments]
        result = self._post("/api/monitors", payload)
        monitor_id = result.get("id", result.get("monitor_id", "unknown"))
        return Response(
            message=f"Monitor created: {name} (id={monitor_id})\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _monitors_get(self, monitor_id="", **kwargs):
        if not monitor_id:
            return Response(message="Provide monitor_id.", break_loop=False)
        result = self._get(f"/api/monitors/{monitor_id}")
        return Response(
            message=f"Monitor {monitor_id}: {json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _monitors_update(self, monitor_id="", **kwargs):
        if not monitor_id:
            return Response(message="Provide monitor_id.", break_loop=False)
        # Pass all remaining kwargs as the update payload
        fields = {k: v for k, v in kwargs.items() if v is not None and v != ""}
        if not fields:
            return Response(message="Provide fields to update (e.g. name, url, schedule, enrichments).", break_loop=False)
        result = self._patch(f"/api/monitors/{monitor_id}", fields)
        return Response(
            message=f"Monitor {monitor_id} updated: {json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _monitors_delete(self, monitor_id="", **kwargs):
        if not monitor_id:
            return Response(message="Provide monitor_id.", break_loop=False)
        self._delete(f"/api/monitors/{monitor_id}")
        return Response(
            message=f"Monitor {monitor_id} deleted.",
            break_loop=False,
        )

    async def _monitors_trigger(self, monitor_id="", **kwargs):
        if not monitor_id:
            return Response(message="Provide monitor_id.", break_loop=False)
        result = self._post(f"/api/monitors/{monitor_id}/trigger", {})
        return Response(
            message=f"Monitor {monitor_id} triggered: {json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _monitors_runs(self, monitor_id="", **kwargs):
        if not monitor_id:
            return Response(message="Provide monitor_id.", break_loop=False)
        result = self._get(f"/api/monitors/{monitor_id}/runs")
        runs = result.get("runs", result) if isinstance(result, dict) else result
        if not runs:
            return Response(message=f"No runs found for monitor {monitor_id}.", break_loop=False)
        if isinstance(runs, list):
            text = f"Runs for monitor {monitor_id} ({len(runs)}):\n"
            for r in runs:
                text += f"- run_id={r.get('id', '?')} status={r.get('status', '?')} started={r.get('started_at', '?')}\n"
        else:
            text = f"Runs: {json.dumps(runs, indent=2)}"
        return Response(message=text, break_loop=False)

    # ── Analytics ─────────────────────────────────────────────────────

    async def _analytics_dashboard(self, **kwargs):
        result = self._get("/api/analytics/dashboard")
        return Response(
            message=f"Analytics dashboard:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _analytics_insights(self, **kwargs):
        result = self._get("/api/analytics/insights")
        return Response(
            message=f"Analytics insights:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _analytics_trending(self, **kwargs):
        result = self._get("/api/analytics/trending")
        return Response(
            message=f"Trending topics:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _analytics_timeline(self, start="", end="", **kwargs):
        params = []
        if start:
            params.append(f"start={start}")
        if end:
            params.append(f"end={end}")
        qs = f"?{'&'.join(params)}" if params else ""
        result = self._get(f"/api/analytics/timeline{qs}")
        return Response(
            message=f"Analytics timeline:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    # ── Enrichments ───────────────────────────────────────────────────

    async def _enrich_item(self, item_id="", plugin="", **kwargs):
        if not item_id or not plugin:
            return Response(message="Provide item_id and plugin.", break_loop=False)
        result = self._post("/api/enrichments/item", {"item_id": item_id, "plugin": plugin})
        return Response(
            message=f"Enrichment queued for item {item_id} with plugin '{plugin}':\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _enrich_batch(self, item_ids=None, plugin="", **kwargs):
        if not item_ids or not plugin:
            return Response(message="Provide item_ids (list) and plugin.", break_loop=False)
        ids = item_ids if isinstance(item_ids, list) else [item_ids]
        result = self._post("/api/enrichments/batch", {"item_ids": ids, "plugin": plugin})
        return Response(
            message=f"Batch enrichment queued for {len(ids)} items with plugin '{plugin}':\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _enrich_webset(self, webset_id="", plugin="", **kwargs):
        if not webset_id or not plugin:
            return Response(message="Provide webset_id and plugin.", break_loop=False)
        result = self._post("/api/enrichments/webset", {"webset_id": webset_id, "plugin": plugin})
        return Response(
            message=f"Webset enrichment queued for webset {webset_id} with plugin '{plugin}':\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _plugins_list(self, **kwargs):
        result = self._get("/api/enrichments/plugins")
        plugins = result.get("plugins", result) if isinstance(result, dict) else result
        if not plugins:
            return Response(message="No enrichment plugins available.", break_loop=False)
        if isinstance(plugins, list):
            text = f"Enrichment plugins ({len(plugins)}):\n"
            for p in plugins:
                if isinstance(p, dict):
                    text += f"- {p.get('name', '?')}: {p.get('description', '')}\n"
                else:
                    text += f"- {p}\n"
        else:
            text = f"Plugins: {json.dumps(plugins, indent=2)}"
        return Response(message=text, break_loop=False)

    # ── Extraction (additional) ───────────────────────────────────────

    async def _extract_batch(self, urls=None, queue="default", enrichments=None, **kwargs):
        if not urls:
            return Response(message="Provide urls (list) to batch extract.", break_loop=False)
        url_list = urls if isinstance(urls, list) else [urls]
        payload = {"urls": url_list, "queue": queue}
        if enrichments:
            payload["enrichments"] = enrichments if isinstance(enrichments, list) else [enrichments]
        result = self._post("/api/extraction/batch", payload)
        return Response(
            message=f"Batch extraction started for {len(url_list)} URLs:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _extract_jobs(self, status="", **kwargs):
        qs = f"?status={status}" if status else ""
        result = self._get(f"/api/extraction/jobs{qs}")
        jobs = result.get("jobs", result) if isinstance(result, dict) else result
        if not jobs:
            return Response(message="No extraction jobs found.", break_loop=False)
        if isinstance(jobs, list):
            text = f"Extraction jobs ({len(jobs)}):\n"
            for j in jobs:
                text += f"- job_id={j.get('job_id', j.get('id', '?'))} status={j.get('status', '?')} url={j.get('url', '?')}\n"
        else:
            text = f"Jobs: {json.dumps(jobs, indent=2)}"
        return Response(message=text, break_loop=False)

    async def _extract_result(self, job_id="", **kwargs):
        if not job_id:
            return Response(message="Provide job_id.", break_loop=False)
        result = self._get(f"/api/extraction/{job_id}/result")
        return Response(
            message=f"Extraction result for {job_id}:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    # ── Webset Items ──────────────────────────────────────────────────

    async def _webset_items(self, webset_id="", limit=50, offset=0, **kwargs):
        if not webset_id:
            return Response(message="Provide webset_id.", break_loop=False)
        params = []
        if limit:
            params.append(f"limit={int(limit)}")
        if offset:
            params.append(f"offset={int(offset)}")
        qs = f"?{'&'.join(params)}" if params else ""
        result = self._get(f"/api/websets/{webset_id}/items{qs}")
        items = result.get("items", result) if isinstance(result, dict) else result
        if not items:
            return Response(message=f"No items in webset {webset_id}.", break_loop=False)
        if isinstance(items, list):
            text = f"Items in webset {webset_id} ({len(items)}):\n"
            for item in items:
                text += f"- {item.get('title', item.get('url', '?'))} (id={item.get('id', '?')})\n"
        else:
            text = f"Items: {json.dumps(items, indent=2)}"
        return Response(message=text, break_loop=False)

    async def _webset_add_item(self, webset_id="", url="", data=None, **kwargs):
        if not webset_id:
            return Response(message="Provide webset_id.", break_loop=False)
        if not url and not data:
            return Response(message="Provide url or data to add.", break_loop=False)
        payload = {}
        if url:
            payload["url"] = url
        if data:
            payload["data"] = data
        result = self._post(f"/api/websets/{webset_id}/items", payload)
        return Response(
            message=f"Item added to webset {webset_id}:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _webset_delete_item(self, webset_id="", item_id="", **kwargs):
        if not webset_id or not item_id:
            return Response(message="Provide webset_id and item_id.", break_loop=False)
        self._delete(f"/api/websets/{webset_id}/items/{item_id}")
        return Response(
            message=f"Item {item_id} deleted from webset {webset_id}.",
            break_loop=False,
        )

    async def _webset_stats(self, webset_id="", **kwargs):
        if not webset_id:
            return Response(message="Provide webset_id.", break_loop=False)
        result = self._get(f"/api/websets/{webset_id}/stats")
        return Response(
            message=f"Stats for webset {webset_id}:\n{json.dumps(result, indent=2)}",
            break_loop=False,
        )

    async def _webset_search(self, webset_id="", query="", limit=10, **kwargs):
        if not webset_id or not query:
            return Response(message="Provide webset_id and query.", break_loop=False)
        result = self._post(f"/api/websets/{webset_id}/search", {"query": query, "limit": int(limit)})
        items = result.get("results", result) if isinstance(result, dict) else result
        if not items:
            return Response(message=f"No results in webset {webset_id} for '{query}'.", break_loop=False)
        if isinstance(items, list):
            text = f"Search results in webset {webset_id} ({len(items)}):\n"
            for item in items:
                text += f"- {item.get('title', 'Untitled')} (score={item.get('score', '?')})\n  URL: {item.get('url', '?')}\n"
        else:
            text = f"Results: {json.dumps(items, indent=2)}"
        return Response(message=text, break_loop=False)

    # ── Export ────────────────────────────────────────────────────────

    async def _export(self, webset_id="", fmt="json", **kwargs):
        if not webset_id:
            return Response(message="Provide webset_id.", break_loop=False)
        content = self._get_raw(f"/api/export/{webset_id}/{fmt}")
        if fmt == "json":
            # Try to pretty-print JSON exports
            try:
                parsed = json.loads(content)
                content = json.dumps(parsed, indent=2)
            except (json.JSONDecodeError, TypeError):
                pass
        return Response(
            message=f"Export ({fmt}) for webset {webset_id}:\n{content}",
            break_loop=False,
        )

    # ── HTTP helpers ──────────────────────────────────────────────────

    def _get(self, path):
        return self._request_with_retry(path, method="GET", timeout=15)

    def _post(self, path, data):
        return self._request_with_retry(path, method="POST", data=data, timeout=30)

    def _patch(self, path, data):
        return self._request_with_retry(path, method="PATCH", data=data, timeout=30)

    def _delete(self, path):
        return self._request_with_retry(path, method="DELETE", timeout=15, expect_empty=True)

    def _get_raw(self, path):
        """GET that returns raw text instead of parsed JSON (for exports)."""
        last_err = None
        for attempt in range(2):
            try:
                req = urllib.request.Request(f"{CRAWLSET_URL}{path}", method="GET")
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read().decode()
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = e
                if attempt < 1:
                    time.sleep(1)
        raise last_err

    def _request_with_retry(self, path, method="GET", data=None, timeout=15, retries=1, expect_empty=False):
        """Execute HTTP request with retry on transient failures."""
        last_err = None
        for attempt in range(1 + retries):
            try:
                req = urllib.request.Request(f"{CRAWLSET_URL}{path}", method=method)
                req.add_header("Content-Type", "application/json")
                if data is not None:
                    body = json.dumps(data).encode()
                    req.data = body
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read().decode()
                    if expect_empty or not raw:
                        return {}
                    return json.loads(raw)
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = e
                if attempt < retries:
                    time.sleep(1)
        raise last_err
