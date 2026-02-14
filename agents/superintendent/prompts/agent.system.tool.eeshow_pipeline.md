### eeshow_pipeline:
Access and manage the EEShow podcast pipeline mounted at /workspace/eeshow-adaptor.
The EEShow pipeline is a 9-phase production system: RSS > transcription > narrative > visuals > social > distribution > international. Key directories: studio/episodes/, tools/, scripts/, transcripts/, narrative/, audio/.
Actions: status, list_episodes, episode_detail, read_file, list_dir, run_script, db_query, rss_sync, canonical_build

**Check pipeline status (mount, database, directories):**
~~~json
{
    "thoughts": ["Checking EEShow pipeline health..."],
    "tool_name": "eeshow_pipeline",
    "tool_args": {
        "action": "status"
    }
}
~~~

**List all episodes in studio/episodes/:**
~~~json
{
    "thoughts": ["Listing available episodes..."],
    "tool_name": "eeshow_pipeline",
    "tool_args": {
        "action": "list_episodes"
    }
}
~~~

**Get detailed file listing for a specific episode:**
~~~json
{
    "thoughts": ["Getting episode detail for ep-21..."],
    "tool_name": "eeshow_pipeline",
    "tool_args": {
        "action": "episode_detail",
        "episode": "ep-21"
    }
}
~~~

**Read a file from the pipeline:**
~~~json
{
    "thoughts": ["Reading the pipeline gates config..."],
    "tool_name": "eeshow_pipeline",
    "tool_args": {
        "action": "read_file",
        "path": "pipeline_gates.yaml"
    }
}
~~~

**List directory contents:**
~~~json
{
    "thoughts": ["Listing tools directory..."],
    "tool_name": "eeshow_pipeline",
    "tool_args": {
        "action": "list_dir",
        "path": "tools"
    }
}
~~~

**Run a pipeline script (.py or .sh only):**
~~~json
{
    "thoughts": ["Running the episode 20 processing script..."],
    "tool_name": "eeshow_pipeline",
    "tool_args": {
        "action": "run_script",
        "script": "scripts/process_episode.py",
        "args": "ep-20"
    }
}
~~~

**Query the pipeline database (read-only SELECT only):**
~~~json
{
    "thoughts": ["Querying episode metadata from pipeline database..."],
    "tool_name": "eeshow_pipeline",
    "tool_args": {
        "action": "db_query",
        "sql": "SELECT * FROM eeshow_anth LIMIT 10"
    }
}
~~~

**Trigger RSS feed sync from Transistor FM:**
~~~json
{
    "thoughts": ["Syncing latest episodes from RSS feed..."],
    "tool_name": "eeshow_pipeline",
    "tool_args": {
        "action": "rss_sync"
    }
}
~~~

**Run 9-step canonical narrative build for an episode:**
~~~json
{
    "thoughts": ["Running canonical build verification for ep-21..."],
    "tool_name": "eeshow_pipeline",
    "tool_args": {
        "action": "canonical_build",
        "episode": "ep-21"
    }
}
~~~
