### boris_strike:
Execute Homeskillet Boris parallel orchestration and EESystem Harpoon compliance scans.
Boris is the Rust orchestration engine. Harpoon is the Aho-Corasick compliance scanner that detects FDA/regulatory violations in content.
Actions: scan, winch, status

**Run Harpoon compliance scan on a directory:**
~~~json
{
    "thoughts": ["Scanning content for compliance violations..."],
    "tool_name": "boris_strike",
    "tool_args": {
        "action": "scan",
        "target_path": "/workspace/operationTorque/src"
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
