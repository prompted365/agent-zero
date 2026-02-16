### crawlset_extract:
Trigger web intelligence operations via the Crawlset pipeline. Crawlset is a full web intelligence system with Playwright crawling, LLM enrichment, Celery task queues, monitors, analytics, and export.

Actions: extract, status, search, websets, create_webset, health, monitors_list, monitors_create, monitors_get, monitors_update, monitors_delete, monitors_trigger, monitors_runs, analytics_dashboard, analytics_insights, analytics_trending, analytics_timeline, enrich_item, enrich_batch, enrich_webset, plugins_list, extract_batch, extract_jobs, extract_result, webset_items, webset_add_item, webset_delete_item, webset_stats, webset_search, export_json, export_csv, export_markdown

#### Core Operations

**Extract intelligence from a URL:**
~~~json
{
    "thoughts": ["Extracting web intelligence from this source..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "extract",
        "url": "https://example.com/article",
        "queue": "realtime"
    }
}
~~~

**Check extraction job status:**
~~~json
{
    "thoughts": ["Checking the extraction job progress..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "status",
        "job_id": "abc-123"
    }
}
~~~

**Search extracted intelligence:**
~~~json
{
    "thoughts": ["Searching extracted intelligence for relevant results..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "search",
        "query": "compliance violations health claims",
        "limit": "10"
    }
}
~~~

**List websets (collections):**
~~~json
{
    "thoughts": ["Listing all websets to see what collections exist..."],
    "tool_name": "crawlset_extract",
    "tool_args": { "action": "websets" }
}
~~~

**Create a new webset:**
~~~json
{
    "thoughts": ["Creating a new webset to organize extracted intelligence..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "create_webset",
        "name": "guest-dossiers",
        "description": "Intelligence on EE.Show guests"
    }
}
~~~

**Check Crawlset system health:**
~~~json
{
    "thoughts": ["Checking if Crawlset services are running..."],
    "tool_name": "crawlset_extract",
    "tool_args": { "action": "health" }
}
~~~

#### Monitor Operations

**List all monitors:**
~~~json
{
    "thoughts": ["Checking what monitors are configured..."],
    "tool_name": "crawlset_extract",
    "tool_args": { "action": "monitors_list" }
}
~~~

**Create a new monitor:**
~~~json
{
    "thoughts": ["Setting up a monitor to track this source on a schedule..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "monitors_create",
        "name": "competitor-blog",
        "url": "https://competitor.com/blog",
        "schedule": "daily",
        "enrichments": ["summarize", "sentiment"]
    }
}
~~~

**Get monitor details:**
~~~json
{
    "thoughts": ["Checking the configuration for this monitor..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "monitors_get",
        "monitor_id": "mon-456"
    }
}
~~~

**Update a monitor:**
~~~json
{
    "thoughts": ["Updating the monitor schedule..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "monitors_update",
        "monitor_id": "mon-456",
        "schedule": "hourly"
    }
}
~~~

**Delete a monitor:**
~~~json
{
    "thoughts": ["Removing this monitor, no longer needed..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "monitors_delete",
        "monitor_id": "mon-456"
    }
}
~~~

**Trigger a monitor run immediately:**
~~~json
{
    "thoughts": ["Triggering an immediate run of this monitor..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "monitors_trigger",
        "monitor_id": "mon-456"
    }
}
~~~

**View monitor run history:**
~~~json
{
    "thoughts": ["Checking the run history for this monitor..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "monitors_runs",
        "monitor_id": "mon-456"
    }
}
~~~

#### Analytics

**View analytics dashboard:**
~~~json
{
    "thoughts": ["Pulling the analytics dashboard for an overview..."],
    "tool_name": "crawlset_extract",
    "tool_args": { "action": "analytics_dashboard" }
}
~~~

**Get AI-generated insights:**
~~~json
{
    "thoughts": ["Getting analytical insights from the intelligence corpus..."],
    "tool_name": "crawlset_extract",
    "tool_args": { "action": "analytics_insights" }
}
~~~

**View trending topics:**
~~~json
{
    "thoughts": ["Checking what topics are trending in extracted intelligence..."],
    "tool_name": "crawlset_extract",
    "tool_args": { "action": "analytics_trending" }
}
~~~

**View extraction timeline (with date range):**
~~~json
{
    "thoughts": ["Pulling extraction activity timeline for the past week..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "analytics_timeline",
        "start": "2026-02-08",
        "end": "2026-02-15"
    }
}
~~~

#### Enrichments

**Enrich a single item:**
~~~json
{
    "thoughts": ["Enriching this extracted item with sentiment analysis..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "enrich_item",
        "item_id": "item-789",
        "plugin": "sentiment"
    }
}
~~~

**Enrich a batch of items:**
~~~json
{
    "thoughts": ["Running batch enrichment on multiple items..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "enrich_batch",
        "item_ids": ["item-001", "item-002", "item-003"],
        "plugin": "summarize"
    }
}
~~~

**Enrich an entire webset:**
~~~json
{
    "thoughts": ["Enriching all items in this webset with entity extraction..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "enrich_webset",
        "webset_id": "ws-123",
        "plugin": "entities"
    }
}
~~~

**List available enrichment plugins:**
~~~json
{
    "thoughts": ["Checking what enrichment plugins are available..."],
    "tool_name": "crawlset_extract",
    "tool_args": { "action": "plugins_list" }
}
~~~

#### Batch Extraction

**Extract multiple URLs in batch:**
~~~json
{
    "thoughts": ["Submitting a batch extraction for multiple URLs..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "extract_batch",
        "urls": ["https://example.com/page1", "https://example.com/page2", "https://example.com/page3"],
        "queue": "default",
        "enrichments": ["summarize"]
    }
}
~~~

**List extraction jobs (optionally filtered by status):**
~~~json
{
    "thoughts": ["Listing all pending extraction jobs..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "extract_jobs",
        "status": "pending"
    }
}
~~~

**Get full result of a completed extraction:**
~~~json
{
    "thoughts": ["Retrieving the full extraction result..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "extract_result",
        "job_id": "abc-123"
    }
}
~~~

#### Webset Management

**List items in a webset:**
~~~json
{
    "thoughts": ["Browsing items in this webset..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "webset_items",
        "webset_id": "ws-123",
        "limit": 20,
        "offset": 0
    }
}
~~~

**Add an item to a webset:**
~~~json
{
    "thoughts": ["Adding this URL to the webset for tracking..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "webset_add_item",
        "webset_id": "ws-123",
        "url": "https://example.com/new-article"
    }
}
~~~

**Delete an item from a webset:**
~~~json
{
    "thoughts": ["Removing this irrelevant item from the webset..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "webset_delete_item",
        "webset_id": "ws-123",
        "item_id": "item-789"
    }
}
~~~

**Get webset statistics:**
~~~json
{
    "thoughts": ["Checking stats for this webset..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "webset_stats",
        "webset_id": "ws-123"
    }
}
~~~

**Search within a specific webset:**
~~~json
{
    "thoughts": ["Searching within this webset for specific intelligence..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "webset_search",
        "webset_id": "ws-123",
        "query": "funding round Series B",
        "limit": 5
    }
}
~~~

#### Export

**Export webset as JSON:**
~~~json
{
    "thoughts": ["Exporting this webset as JSON for downstream processing..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "export_json",
        "webset_id": "ws-123"
    }
}
~~~

**Export webset as CSV:**
~~~json
{
    "thoughts": ["Exporting this webset as CSV for spreadsheet analysis..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "export_csv",
        "webset_id": "ws-123"
    }
}
~~~

**Export webset as Markdown:**
~~~json
{
    "thoughts": ["Exporting this webset as Markdown for documentation..."],
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "export_markdown",
        "webset_id": "ws-123"
    }
}
~~~
