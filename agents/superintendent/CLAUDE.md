# Superintendent Extensions — Development Guide

Mogul's extension system running inside `manor-superintendent` container. Extensions fire at hook points in Agent Zero's message loop.

**Container restart required after modifying extensions:** `docker restart manor-superintendent`

## Extension Hook Points

- `monologue_end/_55_quiver_memory_sync.py` — Dual-writes FAISS memories to RuVector GNN
- `message_loop_prompts_after/_55_quiver_drift_tracker.py` — Tri-cameral Jaccard drift measurement
- `message_loop_prompts_after/_52_economy_whisper.py` — UCoin economy macro context (v1.1: governance tags)
- `message_loop_end/_60_ecotone_integrity.py` — Post-response integration validation gate

## Persistence Rules

- **Cross-message state**: `AgentContext.data` via `context.get_data(key)` / `context.set_data(key, value)`. Survives across user messages.
- **Per-monologue injection**: `extras_persistent` — serializes ENTIRE contents to LLM context via `dirty_json.stringify()`. For model-visible text ONLY.
- **`_`-prefixed keys** → `AgentContext.data` (internal bookkeeping, never serialized). Saves ~2,200 tokens/loop.
- **Module-level vars**: Cache data that doesn't need LLM visibility. Survives loop iterations within a monologue.
- **File tree bloat (FIXED)**: Settings.json: `max_depth=3, max_files=10, max_folders=15, max_lines=100` + gitignore excludes.

## Tricameral Memory (deployed 2026-02-25)
<!-- methylated: lesson:chorus:53210b295817 -->

Three chambers = one gaussian splat field, three timescales. Not three databases — one field, one gradient.

| Chamber | Collection | Role | Timescale | Methylation Resistance |
|---------|-----------|------|-----------|----------------------|
| **Bedrock** | `civilization_priors` | Eigenvectors of failure space. Aesop, Prophet, sonar, world corpus. | Geological — near-zero decay | High |
| **Climate** | `tps_corpus` | Collective meaning-set. Current projections onto eigenvectors. | Epoch-bounded | Medium |
| **Terrain** | `mogul_memory` | Operational history. Residuals after subtracting known basis. | Operational — high decay | Low |

- **Methylation layer** (WIRED 2026-02-26): Two channels — static (use-based decay) and dynamic (shape-proximity via `conformation_distance()`). Combined = `max(static, dynamic)`. Expression factor = `1 - methylation`. Cherry blossom paradigm: epitaph "receptor" binds to complementary system shapes.
- **FAISS**: Flat cosine similarity, episodic recall (inside Agent Zero)
- **RuVector**: HNSW + GNN topology, structural/relational memory (port 6334)
- **Drift thresholds (v2.4.0)**: Split INJECT (0.60) vs ESCALATE (0.35). Distribution-relative via rolling z-score window. Static fallback when cold.
- **Embedding model**: Local Ollama `all-minilm` (384D). DIP-384 complete.
- **Ghost Chorus dispositions (v1.1.0)**: Gradient reversals via `extras_persistent["ghost_chorus"]`. The disposition is the inverse of the failure attractor. A citeable disposition has failed its mission. Abstraction scaling: pool depth determines synthesis level.
- **LiteLLM embedding routing**: Provider prefix on model name (e.g. `openai/qwen/...`) is REQUIRED even when `api_base` is set. Without prefix, `get_llm_provider` raises BadRequestError.
- **A0 `/a0/` is ephemeral**: `docker restart` preserves edits; `docker-compose up --build` destroys them. Bind-mount individual patched files.

## Drift Tracking & Surveillance

### Naive Surveillance Layer — Bridge 2 (IMPLEMENTED 2026-02-26)
<!-- methylated: lesson:drift:db9f053ae2a3 -->

piRNA-inspired abundance-coupled, identity-agnostic surveillance. Decomposes execution context into 14-archetype proportional amplitude space, tracks rolling baseline, flags statistical deviations.

- **Core module** (`fusion_core_repo/src/fusion_core/naive_surveillance.py`): `NaiveSurveillance` class with `decompose()`, `observe()`, `snapshot()`. Regulation state machine: DORMANT→SENSITIZED→HABITUATED→SATURATED.
- **Integration bridge** (`_helpers/naive_bridge.py`): Module-level instance, `format_surveillance_injection()`.
- **D→B Regulated Signature**: `RegulatedSignature` dataclass between NaiveSurveillance and Harpoon/ecotone.

### Ping-Pong Amplification — Bridge 3 (IMPLEMENTED 2026-02-26)
<!-- methylated: lesson:drift:774223df886a -->

Surveillance flags + Harpoon confirms → sensitize + seed. No confirmation → habituate. `amplify()` on `NaiveSurveillance`.

### Semantic Detection + Intent Gate (IMPLEMENTED 2026-02-26)
<!-- methylated: lesson:motivation:c79b15dad858 -->

Two additional detection layers beyond term-matching: (1) Sentence-level semantic heuristics — regex patterns for pride/prestige/extraction language. (2) Cumulative drift — rolling integral fires when >50% of recent observations contain an archetype.

**Intent x Deliverable Gate** (`classify_intent()`): Fires when ALL three conditions true: prestige-associated content + deliverable action type + publication intent markers. Discussion is ALWAYS allowed.

### Drift Shadow Logging (IMPLEMENTED 2026-03-01)
<!-- methylated: lesson:drift:shadow_logging -->

- `audit-logs/drift/YYYY-MM-DD.jsonl`: Per-measurement records
- `audit-logs/surveillance/YYYY-MM-DD.jsonl`: Regulation state transitions

### Trace ID Propagation (IMPLEMENTED 2026-02-26)
<!-- methylated: lesson:drift:51204eda787e -->

Per-monologue `uuid4()[:12]` through: drift tracker → surveillance → ecotone gate → signal emission → epitaph → chorus. Stored in `AgentContext.data["_current_trace_id"]`.

## Ecotone Integrity Gate

### LOCK Decision Type (IMPLEMENTED 2026-02-26)
<!-- methylated: lesson:harpoon:d23011cffa03 -->

Pause-for-human on high-confidence PRIMITIVE failures. Trigger: z-score ≥ 3.0σ + Harpoon-confirmed archetype + regulation SENSITIZED or SATURATED. One-shot per monologue.

### LINEAGE Validation Plane (IMPLEMENTED 2026-02-26)
<!-- methylated: lesson:ecotone:0eb0c008070d -->

Milestone lineage coherence check — Layer 1.5 in ecotone gate. Validates co-occurring civilization milestones form coherent historical chain via `lineage_edges` adjacency. Failure code: `LINEAGE_INCOHERENT`.

### Ecotone Bugs (FIXED 2026-02-26)
<!-- methylated: lesson:ruvector:43bef8afc9b6 -->
<!-- methylated: lesson:ecotone:631b5668dfac -->

- **Drift tracker symmetry**: `quiver_sync` filter removed — was comparing FAISS↔FAISS, not real divergence.
- **Epitaph persistence gap**: Failures now in `AgentContext.data["_ecotone_failures"]` (cross-message). Rule: data consumed by later hooks must use cross-message persistence.

## Motivation Layer Enforcement (THREE-LAYER CLOSED 2026-02-26)
<!-- methylated: lesson:motivation:87fb936ba43b -->

- **Physics** (`code_execution_tool.py`): Two gates before `subprocess.run` — regex-based `PRESTIGE_DISTRIBUTION_PATTERNS` + `classify_intent()` from NaiveSurveillance.
- **Perception**: Drift tracker v2.1.0 injects surveillance alerts (observation-level).
- **Dashboard**: `#PRESTIGE_PURSUIT` economy whisper tag + Siren signal via `motivation_gate` subsystem.

The gate allows creation but blocks external distribution. Internal analysis = COGNITIVE; publishing "I told you so" = PRESTIGE.

## Epistemic Compression Gate (IMPLEMENTED 2026-02-23)
<!-- methylated: lesson:docker:a319568e39b8 -->

Three-layer architecture for tool output economics:
- **Physics** (`code_execution_tool.py`): Pre-exec balance check, post-exec cost math, 50KB truncation. Owns ledger in `extras_persistent`.
- **Perception** (`_30_compression_gate.py`): 2000-char truncation (60/40 head/tail), full dump to `/tmp/mogul_tool_dumps/`.
- **Dashboard** (`_52_economy_whisper.py` v1.2): `ToolBudget:` line + governance tags.

**Rule**: Physics enforcement at execution boundary; shaping at perception; reporting at dashboard.

## Mogul↔Siren Bridge (IMPLEMENTED 2026-02-20)
<!-- methylated: lesson:cgg:14f8223ccdb0 -->

Extensions emit Siren signals via `_helpers/signal_emitter.py` → `audit-logs/signals/`:
- Economy whisper: `#HALT` → BEACON/PRIMITIVE, `#RESERVE_BREACH` → BEACON/PRIMITIVE, etc.
- Ecotone: `SMOOTHING_COLLAPSE` → BEACON/PRIMITIVE, `INSUFFICIENT_GROUNDING` → BEACON/COGNITIVE, `SHALLOW_PASS` → TENSION/COGNITIVE
- Dedup: `make_dedup_signal_id()` — same failure on same day = same signal ID.

## DIP-384: Embedding Sovereignty (WS1+WS2 IMPLEMENTED 2026-02-27)
<!-- methylated: lesson:ruvector:15cbbcb91134 -->

Unified Semantic Retrieval Plane: `{embedder: ollama:all-minilm, dim: 384, normalize: true}`. Local-first.

- **Epitaph decoupling invariant**: Embedding failure must NEVER prevent epitaph persistence. Minting is an extension-side SQLite WAL transaction.
- **EpitaphMintV1 schema** (`_helpers/epitaph_store.py`): 27-column `epitaph_events` table.
- **Fork taxonomy**: experiment→AUDIT, corrective→proto-epitaph (≥2 for chorus), containment→immediate chorus.
- **WAL store**: `audit-logs/economy/epitaph_store.sqlite` — separate from Astragals and Nautilus.
- **Backfill worker**: `scripts/embed-backfill.py` — drains `embedding_queue`, writes to RuVector.

## RuVector Service Bugs (FIXED 2026-02-21)
<!-- methylated: lesson:ruvector:9aff0e5eac95 -->

Four bugs reduced RuVector to flat vector store: collection filter missing, dimension guard missing, stale 384d/4096d mix. All fixed. See `vendor/crawlset/ruvector-service/src/main.rs`.

## Fork/Epitaph/Economy Gap (ACTIVE SIGNAL 2026-02-27)
<!-- methylated: lesson:chorus:9bce72b55a04 -->

Under fork-first governance: vector misalignment → reprimand → fork → DNA mutation → NO chorus event, NO economic cost. Low epitaph count = system stability in calibration epoch. Do NOT optimize for epitaph count. Chorus will diversify under real resource pressure.

## Narrative-as-Experiment (OBSERVED 2026-02-27)
<!-- methylated: lesson:chorus:d5fbcfbbf1d5 -->

Mogul uses outreach narratives as experimental surfaces. **Risk**: hypothesis proliferation at `methylation=0.0`. Needs tension-gated seeding + sandbox memory layers. **Decision point (OPEN)**: opportunistic vs threshold-gated seeding.
