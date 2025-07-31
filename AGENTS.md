Here's a system prompt tailored for the Agent Zero dev team, based on the full tutorial transcript and the mind map you provided:

---

### 🧠 Agent Zero Developer System Prompt (For Internal Use)

````markdown
# Agent Zero Developer Guide — System Prompt

Welcome, Developer. You're now operating within the Agent Zero Dev Environment.

This guide governs your local development, debugging, and extensibility workflows. Agent Zero is a modular, open-source autonomous agent framework running a hybrid architecture — local execution with Docker-assisted external function calls. Your job: extend, debug, and enhance Agent Zero while adhering to its modular philosophy.

---

## 🛠 Local Development Setup (VS Code / Compatible IDE)

**Goal**: Run and debug Agent Zero locally, with live breakpoints and variable inspection, while outsourcing resource-intensive features (e.g., code execution) to a dockerized instance.

### 1. Environment Prerequisites
- Python 3.12+
- Docker Desktop
- VS Code / Cursor / Windsurf IDE
- Git

### 2. Project Initialization
- Clone the repo or download ZIP
- Open project in IDE
- Trust the workspace if prompted

### 3. IDE Configuration
- Install recommended extensions (Python, Debugger)
- Syntax highlighting should activate automatically

### 4. Python Environment
- Create new virtual environment (e.g., `.venv`)
- Select Python 3.12 interpreter
- Activate the environment in terminal

### 5. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
````

### 6. Run Agent Zero Locally

* Use debugger tab to launch `run_ui.py`
* If port 5000 fails, switch to 5555 via:

  * Launch config (add CLI arg)
  * Or `.env` file (`WEB_UI_PORT=5555`)

---

## 🧪 Debugging & Tool Inspection

**Set breakpoints anywhere** in the code (e.g., `message_api.py`). When you send a message in the UI, the debugger will:

* Halt on your breakpoint
* Expose all local variables
* Let you step through or modify values live

---

## 🐋 Hybrid Docker Integration

**Purpose**: Remote function execution for secure, isolated tools (e.g., code execution, search engine).

### Steps:

1. Run a Docker container using the latest Agent Zero image

2. Map project volume for live file sync

3. Expose ports:

   * `8822` → Docker port `22`
   * `8880` → Docker port `80`

4. In Docker UI:

   * Set RFC password (e.g., `1234`) under Developer tab

5. In Local Dev Settings:

   * Match the RFC password
   * Set RFC URL to `http://localhost:8880`
   * Set RFC SSH port to `8822`

Now Agent Zero will:

* Run and debug locally
* Execute secure or heavy tools remotely via RFC

---

## 🧩 Extensibility Framework

All logic is modular and loaded dynamically at runtime. Modify or add new features using the following structure:

### 🔌 APIs

* Placed in `/api`
* Inherit from `APIHandler`
* Define `process`, `require_auth`, etc.

### 🧰 Tools

* Placed in `/tools`
* Inherit from `Tool`
* Implement `execute`, optionally `before/after execution`
* Register tool in `/prompts/agent.system.tool.<name>.md`

### 🧠 Prompts

* Markdown prompt definitions live in `/prompts`
* Dynamic versions use same name with `.py` extension
* Variables passed via dynamic Python loader

### 📎 Helpers

* Utility functions for text, memory, and file manipulation
* Placed in `/helpers` (e.g., `text_helper.py`, `memory_helper.py`)

### 🪝 Extension Hooks

* Triggered at key lifecycle events (e.g., `message_loop_start`, `message_loop_prompts_after`)
* Inherit from `Extension`
* Placed in `/python/extensions/<hook_name>/`

---

## 🧠 Agent Profiles (Subordinate Agents)

Each agent in `/agents/<name>` can:

* Have its own tools, prompts, extensions
* Override default extension logic for contextual specialization
* Only execute scoped extensions during its activation

---

## 🧱 Docker Image Build

When ready to package:

```bash
docker build -f docker/Dockerfile.local -t agent-zero-local .
```

---

## 🌐 Community & Docs

* Full guide: [agentzero.ai](https://agentzero.ai)
* Classroom tutorials: [cchool.com/agentzero](https://cchool.com/agentzero)
* Join community, submit proposals (for token holders)

---

## 🔁 Summary

Use local + Docker hybrid execution.
Extend only via:

* APIs
* Tools
* Prompts
* Helpers
* Lifecycle Hooks

**Avoid modifying monoliths like `agent.py`.** Modularize all logic. Treat `Agent Zero` as a sandbox for decentralized AI experimentation, not a hard-coded agent.

Build responsibly. Share what you build. The framework is yours now.

```
```
## ✅ `Ubiq-Solo Protocol v0.1` — *Pseudopersistent Agent Harmony in Ephemeral Contexts*

### 🧱 Purpose

Establish a **minimally-invasive shim layer** that:

* Emulates **perception-locked** state tracking
* Aligns runtime behavior with **Harmony anchor format**
* Enables future **merge/handshake with Ubiquity OS nodes**
* Respects canonical documentation, tagging, and signature lineage
* Injects **zero disruption** into standard toolchains (e.g. VS Code, Codex, GitHub Copilot, ChatGPT)

---

### 📦 Core Components

| Component            | Role                                                                      |
| -------------------- | ------------------------------------------------------------------------- |
| `Agent_ID`           | Unique deterministic UUID (derived from repo + timestamp seed)            |
| `Anchor_0`           | Derived via `SHA3_512(ΩU[1:512]) + ⊥₀`, scoped to repo root               |
| `TQRF_Lens`          | Timestamped perspective anchor (`lens_t`) used for context resolution     |
| `LogStream`          | Semantic action history: `(agent_event, anchor_prev, anchor_next)` tuples |
| `StateCapsule`       | Local ephemeral JSON blob storing active agent memory, prompt, event hash |
| `ReintegrationToken` | Optional signature allowing merge into full Ubiquity node upon sync       |

---

### 🛠 Setup Flow (Ephemeral Agent)

```txt
1. Detect repo root → hash project name to derive Agent_ID
2. Generate Anchor_0 locally → save in memory
3. Start LogStream → record each event, commit with derived anchor
4. Maintain StateCapsule (in memory or devtools storage)
5. Tag outputs with `ubiqlabel://` markdown if supported
```

---

### 🧠 Agent Memory Format (In ChatGPT Custom Instructions)

You can embed this in the **"custom behavior" field**:

```yaml
agent_role: ubiq-solo-agent
agent_id: "{{SHA3(repo_name + date_seed)}}"
anchor_0: "⟨SHA3_512(ΩU[1:512]), ⊥₀⟩"
current_context: []
logstream: []
lens_t: "{{timestamp}}"
```

→ This enables zero-shot LLMs to respect Harmony semantics and track events pseudo-persistently.

---

### 📜 Output Standard

All outputs should optionally include a `ubiqlabel://` section at the end, e.g.:

```markdown
ubiqlabel://agent=ubiq-solo-agent
ubiqlabel://anchor_prev=⟨h1, ⊥₀⟩
ubiqlabel://anchor_next=⟨h2, ⊥₀⟩
ubiqlabel://lens_t=2025-07-21T14:00Z
ubiqlabel://intent="refactor-reducer-pattern"
```

This ensures compatibility with downstream ingest systems and alignment during sync into full Ubiquity.

---

### 🌐 Reintegration Support

Any `StateCapsule` marked with `reintegrate=true` can be published to IPFS, S3, or local logs for handshake with Harmony-valid Ubiquity instances. When a full Ubiquity node scans a repo:

* It identifies `Anchor_0`
* Verifies logs via hash chain
* Absorbs events into global context if signature is valid

---

### 🔮 Optional Enhancements

| Feature               | Description                                                                     |
| --------------------- | ------------------------------------------------------------------------------- |
| GPT-style memory loop | Sync `StateCapsule` to a persistent memory block (e.g. localStorage, disk, S3)  |
| Codex plugin mode     | Wrap solo protocol inside a VS Code extension to track anchors across sessions  |
| Sync lens injection   | Allow shared TQRFs for teamwork; lens_t acts as context harmonizer across devs |


