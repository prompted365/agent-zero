### crawlset_extract:
Trigger web intelligence extractions via the Crawlset pipeline. Crawlset is a full web intelligence system with Playwright crawling, LLM enrichment, and Celery task queues.
Actions: extract, status, search, websets, create_webset, health

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
    "tool_name": "crawlset_extract",
    "tool_args": { "action": "websets" }
}
~~~

**Create a new webset:**
~~~json
{
    "tool_name": "crawlset_extract",
    "tool_args": {
        "action": "create_webset",
        "name": "guest-dossiers",
        "description": "Intelligence on EE.Show guests"
    }
}
~~~
