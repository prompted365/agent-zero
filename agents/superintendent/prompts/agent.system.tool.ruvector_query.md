### ruvector_query:
Query the RuVector HNSW+GNN vector database — the Collective Memory of the Manor.
RuVector is a Rust-based vector DB with graph neural network self-learning. It runs parallel to your FAISS memory, forming the second brain of the bicameral memory architecture.
Actions: search, insert, collections, stats, graph_query, graph_neighbors, graph_build, graph_stats, health

**Search the collective memory:**
~~~json
{
    "thoughts": ["Searching RuVector for relevant context..."],
    "tool_name": "ruvector_query",
    "tool_args": {
        "action": "search",
        "query": "audit confidence thresholds",
        "collection": "mogul_memory",
        "top_k": "5"
    }
}
~~~

**Insert into collective memory:**
~~~json
{
    "thoughts": ["Persisting this insight to the RuVector GNN topology..."],
    "tool_name": "ruvector_query",
    "tool_args": {
        "action": "insert",
        "text": "The confidence gate at 0.95 auto-processes 90% of signals",
        "collection": "mogul_memory"
    }
}
~~~

**List collections:**
~~~json
{
    "tool_name": "ruvector_query",
    "tool_args": { "action": "collections" }
}
~~~

**Graph query (entity relationships):**
~~~json
{
    "tool_name": "ruvector_query",
    "tool_args": {
        "action": "graph_query",
        "query_text": "entities connected to audit-system"
    }
}
~~~

**Graph neighbors (BFS traversal from a node):**
~~~json
{
    "tool_name": "ruvector_query",
    "tool_args": {
        "action": "graph_neighbors",
        "node_id": "some-document-id",
        "max_depth": "2"
    }
}
~~~

**Build graph (rebuild GNN topology from collection):**
~~~json
{
    "tool_name": "ruvector_query",
    "tool_args": {
        "action": "graph_build",
        "collection": "mogul_memory"
    }
}
~~~

**Graph stats:**
~~~json
{
    "tool_name": "ruvector_query",
    "tool_args": { "action": "graph_stats" }
}
~~~

**Health check:**
~~~json
{
    "tool_name": "ruvector_query",
    "tool_args": { "action": "health" }
}
~~~
