### boris_strike:
Execute Homeskillet Boris parallel orchestration and Harpoon pattern anchor scans.
Boris is the Rust orchestration engine. Harpoon is the domain-agnostic Aho-Corasick pattern anchor engine that identifies fixed points (anchors) in text pattern-space.
Actions: scan, module_scan, session_scan, winch, status

**Run Harpoon pattern anchor scan on a directory:**
~~~json
{
    "thoughts": ["Scanning content for pattern anchors..."],
    "tool_name": "boris_strike",
    "tool_args": {
        "action": "scan",
        "target_path": "/workspace/operationTorque/src"
    }
}
~~~

**Run composable module scan (all always_on modules):**
~~~json
{
    "thoughts": ["Running modular pattern anchor scan with all active modules..."],
    "tool_name": "boris_strike",
    "tool_args": {
        "action": "module_scan",
        "target_path": "/workspace/operationTorque/src"
    }
}
~~~

**Run module scan filtered by domain:**
~~~json
{
    "thoughts": ["Anchoring against canon governance patterns..."],
    "tool_name": "boris_strike",
    "tool_args": {
        "action": "module_scan",
        "target_path": "/workspace/operationTorque/docs",
        "domain": "canon"
    }
}
~~~

**Run module scan with specific modules:**
~~~json
{
    "thoughts": ["Anchoring against solar claims patterns..."],
    "tool_name": "boris_strike",
    "tool_args": {
        "action": "module_scan",
        "target_path": "/workspace/operationTorque/src",
        "modules": "solar_claims,fda_extended"
    }
}
~~~

**List all available pattern modules:**
~~~json
{
    "thoughts": ["Listing available pattern modules..."],
    "tool_name": "boris_strike",
    "tool_args": {
        "action": "module_scan",
        "list_modules": true
    }
}
~~~

**Run session scan with anchor tension pairing (pairs pattern anchors with ecotone state):**
~~~json
{
    "thoughts": ["Scanning session data for pattern anchors paired with tension trajectories..."],
    "tool_name": "boris_strike",
    "tool_args": {
        "action": "session_scan",
        "target_path": "/workspace/operationTorque/audit-logs/ecotone/2026-02-15.jsonl",
        "domain": "lifecycle.mogul",
        "ecotone_log_dir": "/workspace/operationTorque/audit-logs/ecotone",
        "session_date": "2026-02-15",
        "output": "json"
    }
}
~~~

**Execute Boris parallel winch orchestration:**
~~~json
{
    "thoughts": ["Triggering Boris parallel orchestration..."],
    "tool_name": "boris_strike",
    "tool_args": {
        "action": "winch"
    }
}
~~~

**Check Rust toolchain and crate availability:**
~~~json
{
    "tool_name": "boris_strike",
    "tool_args": { "action": "status" }
}
~~~
