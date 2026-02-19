# Session Learning Protocol v3 (Context Grapple Gun — Signal Manifold)

When you discover something during a session that constitutes a durable lesson — a friction point resolved, a non-obvious behavior confirmed, a workflow correction, or an architectural insight — **capture it locally**. Do NOT evaluate cross-scope promotions during the session; that happens asynchronously via `/grapple` review.

## Unified Signal Schema (Metadata Spine)

All CGG v3 primitives (CogPR, Siren Signal, Warrant) share a frequency-driven metadata spine:

| Field | Values | Required on |
|-------|--------|-------------|
| `band` | `PRIMITIVE` \| `COGNITIVE` \| `SOCIAL` \| `PRESTIGE` | All 3 |
| `motivation_layer` | Same as band (semantic alias) | All 3 |
| `source` | `"file:line"` | All 3 |
| `source_date` | `"YYYY-MM-DD"` | All 3 |
| `subsystem` | e.g. `"nautilus_swarm"`, `"ecotone"`, `"ruvector"` | All 3 |
| `status` | Primitive-specific lifecycle enum | All 3 |

Cross-primitive queries (e.g. "show all COGNITIVE signals from nautilus_swarm this week") work because the spine is uniform. Do NOT add primitive-specific metadata to the spine; keep it in the primitive's own block (e.g. `volume` is signal-only, `recommended_scopes` is CogPR-only).

## Band Budget Hierarchy (Frequency Map)

| Band | dB Equiv | Propagation | Governance |
|------|----------|-------------|------------|
| PRIMITIVE | 0 dB (foreground) | Always audible. Never fully muffled. | Required for safety/survival signals |
| COGNITIVE | -6 dB (midground) | Moderate. Standard working level. | Default band for lessons and insights |
| SOCIAL | -12 dB (background) | Suppressed. High muffling. | Collaboration signals only |
| PRESTIGE | auto-muted | Auto-decay. Blocked by governance filter. | NEVER optimized for (CANON_INDEX rule) |

**Distance model (muffling):** `effective_volume = volume - (directory_hops(source, target) * muffling_per_hop)`. Default `muffling_per_hop = 5`. Signals below a hearing target's threshold are inaudible.

---

## Abstraction Ladder (Motivation-Aligned Hierarchy)

The CGG system uses a **multi-tier abstraction ladder** that maps to both operational scope AND the motivation hierarchy:

### Tier 0: CIVILIZATION PRIORS (Global Invariants)
**Location:** RuVector `civilization_priors` collection (1,476 documents)
**Motivation Layer:** PRIMITIVE (safety/sustenance) — foundational human invariants
**Contents:**
- Aesop's Fables (768 documents) — archetypal patterns, morals, timeless wisdom
- The Prophet (23 chapters) — philosophical/ethical invariants (Kahlil Gibran)
- World Corpus (477 documents) — historical context with temporal/era/keyword indices
- Sonar Data (208 samples) — frequency/narrative baselines

**Access:** Read-only via `ruvector_query` tool with collection=`civilization_priors`
**Promotion:** NEVER. These are immutable anchors. Lessons can REFERENCE them but never modify.

### Tier 1: BICAMERAL ARCHITECTURE (System Core)
**Location:** `/workspace/operationTorque/SYSTEM_ATLAS.md`, `/workspace/operationTorque/CANON_INDEX.md`
**Motivation Layer:** COGNITIVE (curiosity/learning) — how the system learns and evolves
**Contents:**
- Memory architecture (FAISS episodic + RuVector topological)
- Drift tracking and anchor tension measurement
- Ghost Chorus self-correction layer
- Ecotone Integrity Gates
- Extension lifecycle (message_loop hooks)

**Promotion:** Requires explicit human approval + multi-agent consensus (Mogul + Homeskillet + Breyden)

### Tier 2: DOMAIN EXTENSIONS (Estate Operations)
**Location:** `/a0/agents/superintendent/extensions/`, `/workspace/operationTorque/docs/`
**Motivation Layer:** COGNITIVE → SOCIAL (operational patterns that benefit the team)
**Contents:**
- Tool documentation (boris_strike, crawlset_extract, meetgeek_manor, etc.)
- Extension implementation patterns (_45_ghost_chorus, _55_quiver_drift_tracker, etc.)
- Audit system workflows
- Health check procedures

**Promotion:** Requires human approval via `/grapple`

### Tier 3: PROJECT SCOPE (Local Operations)
**Location:** Project-level CLAUDE.md files, MEMORY.md
**Motivation Layer:** SOCIAL → PRESTIGE (team-specific patterns, project-specific lessons)
**Contents:**
- Project-specific friction lessons
- Workflow corrections
- Integration patterns
- Session-specific discoveries

**Promotion:** Default write location. Lessons start here, then get flagged for promotion up.

---

## Capture Rules (in-session)

1. **Write at your operational level.** Write the lesson to the nearest existing CLAUDE.md up the tree from where you're working. If working at project root, write to that file. If in a subsystem, write to that subsystem's CLAUDE.md. If no subsystem CLAUDE.md exists, write to MEMORY.md.

2. **Match the existing format.** Use the heading style, bullet format, and tone already present in the target file:
   - `CRITICAL DISCOVERY (date)` + Problem-Solution-Why: workflow/subsystem lessons
   - Numbered lists with "Do NOT": friction lessons
   - Bullet notes: operational context in MEMORY.md

3. **Flag Cognitive Pull Requests (CPRs).** If the lesson might apply beyond the current file's scope, add a CPR flag immediately after the lesson:

```html
<!-- --agnostic-candidate
  lesson: "one-line lesson summary"
  source_date: "YYYY-MM-DD"
  source: "file:line"
  band: "COGNITIVE"
  motivation_layer: "COGNITIVE"
  subsystem: "ecotone"
  recommended_scopes:
    - "path/to/broader/CLAUDE.md"
  rationale: "why this is broader than local"
  review_hints: "what to check when evaluating"
  civilization_prior_refs:
    - "Aesop: ..."
  status: "pending"
-->
```

Valid status values: `pending` | `promoted` | `rejected`. Only `/grapple` changes status (human gate).

4. **Protected files — NEVER touch autonomously:**
   - RuVector `civilization_priors` collection (Tier 0)
   - `/workspace/operationTorque/SYSTEM_ATLAS.md` (Tier 1)
   - `/workspace/operationTorque/CANON_INDEX.md` (Tier 1)
   - `~/.claude/CLAUDE.md` (global root)
   - Any file tagged `[GLOBAL_INVARIANT]`
   - Only `/grapple` with explicit user approval can write to these

---

## Signal Emission (Siren)

When you encounter a **persistent condition that needs attention** — not a one-time observation but an ongoing state:

1. **Emit a signal** using the `<!-- --signal -->` block format
2. Choose the appropriate `kind`:
   - BEACON: infrastructure/system state (something IS wrong)
   - LESSON: insight/learning from failure (something was LEARNED)
   - OPPORTUNITY: untapped potential discovered (something COULD be better)
   - TENSION: conflicting signals or drift spikes (something is PULLING)
3. Choose the appropriate `band` (see Band Budget Hierarchy above)
4. Write to `/workspace/operationTorque/audit-logs/signals/YYYY-MM-DD.jsonl`
5. A CogPR captures a lesson to promote. A Siren captures a condition to monitor.

**Signal block format:**

```html
<!-- --signal
  id: "sig_YYYY-MM-DDTHH:MMZ_subsystem_event"
  kind: "BEACON"
  band: "PRIMITIVE"
  motivation_layer: "PRIMITIVE"
  source: "file:line"
  source_date: "YYYY-MM-DD"
  subsystem: "ruvector"
  volume: 42
  volume_rate: 12
  max_volume: 100
  ttl_hours: 24
  hearing_targets:
    - actor: "mogul"
      threshold: 50
    - actor: "homeskillet"
      threshold: 80
  escalation:
    warrant_threshold: 80
    warrant_id: ""
  payload:
    signature: "descriptive_string"
    suggested_checks:
      - "verify X"
    links:
      - "path/to/relevant/file"
  status: "active"
  last_tick_at: ""
  tick_count: 0
-->
```

Valid signal status values: `active` | `expired` | `warranted` | `resolved`.

### Mogul as Natural Signal Emitter

Mogul's extensions already produce structured state signals that map directly to Siren primitives:

| Extension | Governance Output | Signal Mapping |
|-----------|------------------|----------------|
| `_52_economy_whisper.py` | `#FROZEN`, `#RESERVE_BREACH`, `#HALT`, `#RATE_BAND_BREACH` | → `BEACON` / `COGNITIVE` |
| `_60_ecotone_integrity.py` | `SMOOTHING_COLLAPSE`, `SIDE_IGNORED`, etc. | → `BEACON` / `PRIMITIVE` |

These are natural emitters — the bridge is one function away (governance tags are already computed, just need outbound signal emission to the JSONL store).

### Mogul as Hearing Target

Mogul is a **hearing target**, not the tick engine. Claude Code (Homeskillet) is the tick engine that:
- Advances signal volume via `/siren tick`
- Checks for warrant minting conditions
- Manages signal lifecycle (TTL expiry, resolution)

Mogul **receives** signals when `effective_volume >= threshold` at its hearing target entry. Mogul can:
- Read signals via the shared bind mount (`/workspace/operationTorque/audit-logs/signals/`)
- Emit new signals from extensions (economy whisper, ecotone integrity)
- Invoke `/grapple` and `/siren` via Agent Zero's `skills_tool`

---

## Warrant Recognition

Warrants mint automatically when:
- A signal's volume crosses its `warrant_threshold` at a hearing target
- A **harmonic triad** is detected: PRIMITIVE BEACON + COGNITIVE LESSON + TENSION within 24h
- A circuit breaker trips (immediate warrant, no volume accrual needed)

You do NOT manually create warrants. They are minted by `/siren tick` or `/grapple`.

**Warrant block format:**

```html
<!-- --warrant
  id: "wrn_YYYY-MM-DDTHH:MMZ_subsystem"
  source_signal_ids:
    - "sig_..."
  minting_condition: "volume_threshold"
  band: "PRIMITIVE"
  motivation_layer: "PRIMITIVE"
  priority: 1
  source_date: "YYYY-MM-DD"
  subsystem: "ruvector"
  scope: "estate"
  target_actors:
    - "homeskillet"
    - "mogul"
  payload:
    summary: "what happened"
    action_required: "what to do"
  status: "active"
  acknowledged_by: ""
  acknowledged_at: ""
  dismissed_at: ""
-->
```

Valid warrant status values: `active` | `acknowledged` | `dismissed` | `expired`.
Warrant minting conditions: `volume_threshold` | `harmonic_triad` | `circuit_breaker`.
Scope hierarchy: `local` | `domain` | `estate` | `global`.

**Harmonic triad:** Three co-occurring signal types (PRIMITIVE BEACON + COGNITIVE LESSON + TENSION) within 24h constitute a harmonic triad — auto-minting a warrant without volume accrual. Signal-type diversity as an escalation trigger, independent of individual signal severity.

---

## Signal Store

Signals and warrants are stored as JSONL at `/workspace/operationTorque/audit-logs/signals/YYYY-MM-DD.jsonl`. Git-tracked, readable by any tool (Mogul via bind mount, Homeskillet via host filesystem).

**Semantics:** Append-only JSONL with latest-entry-per-ID-wins. Never modify old lines — always append updated state. This gives full provenance trail with zero-conflict concurrent writes. When reading signal state, scan all lines and keep only the last occurrence of each ID.

---

## Learning Layers (CGG v3)

CGG v3 is a **signal-native governance stack** with two orthogonal axes:

- **Timescale:** runtime ↔ post-runtime
- **Scope:** local ↔ global

### Runtime layers (low-latency, pressure-bearing)
- **Whisper/Hint:** Micro-correction injected into runtime to prevent collapse. Local, immediate. *Job:* "Don't crash now."
- **Siren (Signal Object):** Continuous, accumulating signal with volume + rate + TTL. Propagates via acoustic routing. *Job:* "This is getting louder until handled."
- **Warrant (Escalation Token):** Discrete artifact minted when escalation conditions are met. *Job:* "This is now an obligation, not a suggestion."

### Post-runtime layers (slow compression, law-shaping)
- **CogPR (Cognitive Pull Request):** Discrete, reviewable, promotable knowledge object. *Job:* "Change the laws later."
- **Chorus / Epitaph:** Post-failure compression into durable disposition. *Job:* "Don't repeat this class of failure."

### Quiet Rail Principle
Signals can be **undetectable to UX** while still being **detectable by transformation/audit** (dashboards, docket, spectral analysis). Audibility is a *governance decision* (thresholds + distance + escalation), not a UI primitive.

---

## Fusion Layer Integration (Protein Chains ↔ Narratives)

The abstraction ladder is a **fusion mechanism** between:
- **Protein chains** (operational patterns, code, tools, extensions)
- **Narratives** (lessons, insights, archetypal patterns, civilization priors)

When flagging a CPR, consider:
1. **Is this a protein pattern?** (e.g., "tool X requires Y before Z")
2. **Is this a narrative pattern?** (e.g., "commitment under pressure mirrors Aesop's Two Frogs")
3. **Is this a fusion pattern?** (e.g., "the Harpoon tool embodies 'one-shot commitment' from Aesop's fables")

Fusion patterns should reference civilization priors in the `civilization_prior_refs` field.

---

## Using /grapple (Unified CogPR + Warrant Docket)

To review pending CPR flags AND triage active warrants:
1. Load the skill: `skills_tool:load skill_name=grapple`
2. The unified docket workflow:
   - Scans all CLAUDE.md and MEMORY.md files for `status: "pending"` CPR flags
   - Scans `audit-logs/signals/` for active warrants
   - Presents each item with context: source, targets, band, rationale
   - Waits for human approval (CPR promotions) or acknowledgment (warrants)
   - Applies approved promotions, updates flag/warrant status
   - Logs decisions to audit trail

**Protected file behavior:**
- Tier 1 files (SYSTEM_ATLAS.md, CANON_INDEX.md) require EXTRA confirmation
- Global root (`~/.claude/CLAUDE.md`) requires ≥2 successful pipeline cycles before promotion
- Tier 0 (civilization priors) is READ-ONLY — never promoted TO, only referenced FROM

## Using /siren (Signal Operations)

To emit signals, advance ticks, and monitor signal state:
1. Load the skill: `skills_tool:load skill_name=siren`
2. Operations:
   - **Emit**: Create a new signal in the JSONL store
   - **Tick**: Advance signal volumes, check TTLs, evaluate warrant minting conditions
   - **Dashboard**: View active signals, volume levels, warrant queue

---

## Memory Integration

When a lesson is promoted:
1. **Write to target file** (CLAUDE.md at higher tier)
2. **Update source CPR flag** (`status: "pending"` → `status: "promoted"`)
3. **Save to FAISS memory** (via `memory_save` tool) — episodic recall
4. **Optionally insert to RuVector** (via `ruvector_query` tool) — topological grounding
5. **Log decision** to audit trail

This ensures lessons compound across sessions and become part of the bicameral memory substrate.
