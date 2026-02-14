### boris_strike:
Execute Homeskillet Boris parallel orchestration and Harpoon compliance scans.
Boris is the Rust orchestration engine. Harpoon is the domain-agnostic Aho-Corasick compliance scanner that detects regulatory violations in content.
Actions: scan, module_scan, winch, status

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

**Run composable module scan (all always_on modules):**
~~~json
{
    "thoughts": ["Running modular compliance scan with all active modules..."],
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
    "thoughts": ["Scanning with canon governance modules..."],
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
    "thoughts": ["Scanning with solar claims compliance..."],
    "tool_name": "boris_strike",
    "tool_args": {
        "action": "module_scan",
        "target_path": "/workspace/operationTorque/src",
        "modules": "solar_claims,fda_extended"
    }
}
~~~

**List all available compliance modules:**
~~~json
{
    "thoughts": ["Listing available compliance modules..."],
    "tool_name": "boris_strike",
    "tool_args": {
        "action": "module_scan",
        "list_modules": true
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
