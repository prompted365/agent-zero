### foreman_economy:
Read-only query tool for the Nautilus Swarm economy Foreman. Returns economy snapshots, barometer state, prospector ideas, and health status. All operations are non-mutating reads from lock-free snapshots.

Actions: snapshot, barometer, health, ideas

**Get full economy snapshot (supply, rate, reserves, breach flags, staleness):**
~~~json
{
    "thoughts": ["Check the current economy state — reserve ratio and mint status"],
    "tool_name": "foreman_economy",
    "tool_args": {
        "action": "snapshot"
    }
}
~~~

**Check barometer phase and trend:**
~~~json
{
    "tool_name": "foreman_economy",
    "tool_args": {
        "action": "barometer"
    }
}
~~~

**Health check (is the Foreman reachable?):**
~~~json
{
    "tool_name": "foreman_economy",
    "tool_args": {
        "action": "health"
    }
}
~~~

**Get prospector ideas (opportunities, suggestions, signals):**
~~~json
{
    "tool_name": "foreman_economy",
    "tool_args": {
        "action": "ideas"
    }
}
~~~
