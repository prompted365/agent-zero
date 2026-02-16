# Harpoon: Pattern Anchor Engine

## What Harpoon IS

Harpoon is a **domain-agnostic Aho-Corasick pattern anchor engine** that identifies fixed points (anchors) in text pattern-space. It is NOT a "compliance scanner" — compliance is merely one application domain. Harpoon's core function is to locate immutable reference points in any text stream, providing structural coordinates for downstream reasoning.

An anchor is a fixed point in pattern-space: a known term, phrase, or signal whose presence (or absence) in a text establishes a factual coordinate. Just as a physical anchor holds position against current, a pattern anchor holds semantic position against narrative drift.

## Core Concepts

### PatternMatch = Anchor

A `PatternMatch` is an **anchor** — a fixed point detected in text. It is NOT a "violation." When Harpoon finds a match, it has located a known coordinate in pattern-space. What that coordinate *means* depends on the module, the severity tier, and the covenant that governs the scan.

Each anchor carries **provenance**: which module defined it, which domain it belongs to, its severity tier, byte position in the source text, and a context window around the match. This provenance is what makes anchors useful — you always know exactly where a signal came from and why it was registered.

### CompositeGuard = Anchor Automaton

The `CompositeGuard` is an **anchor automaton** — a single Aho-Corasick automaton compiled from one or more pattern modules. When multiple modules are loaded (e.g., `fda_core` + `governance` + `zone_signals`), their patterns are composed into one automaton that scans in a single pass. This is the engine's key efficiency: regardless of how many modules are active, the text is traversed exactly once.

The automaton is composed per severity tier. Three tiers means three automata, each scanning independently but in the same pass over the text.

### Three Severity Tiers (Reframed)

| Tier | Anchor Type | Behavior | Purpose |
|------|-------------|----------|---------|
| **Critical** | Hard anchor | Immovable. Pipeline halts. | Non-negotiable fixed points — patterns whose presence demands immediate action. FDA prohibited claims, safety-critical language. |
| **Warning** | Soft anchor | Flagged for audit. Continues. | Significant coordinates that require human awareness but don't block progress. Logged with full provenance. |
| **Detect** | Signal anchor | Classification only. No action. | General signal identification — archetypes, narrative zones, behavioral markers, civilization patterns. Reported with provenance but triggers no enforcement. This is what makes Harpoon a *general* pattern engine, not just a compliance tool. |

The **Detect** tier is the key insight: it transforms Aho-Corasick from a blocking/flagging mechanism into a universal signal classifier. The `narrative/zone_signals.json` module uses Detect to classify content into narrative zones. The `canon/governance.json` module uses Detect to identify policy drift language. The civilization priors modules (Aesop, Prophet, sonar, world corpus) use Detect to recognize archetypal and historical patterns in text.

### Winch = Tension System

The **Winch** is the tension measurement system that quantifies the gap between anchors found and the target state. Think of it as the mechanism that measures how much slack or strain exists between where you are (current anchor constellation) and where you should be (covenant specification).

Winch computes:
- **Anchor coverage**: Which expected anchors were found vs. missing
- **Unexpected anchors**: Anchors found that the covenant did not anticipate
- **Tension score**: A scalar measure of the gap between current state and target state
- **Directional tension**: Whether the gap is narrowing (resolving) or widening (diverging) over successive scans

### Covenant = Reality-to-Target Contract

A **Covenant** is a reality-to-target contract. It defines:
- **WHAT** patterns should be present or absent in the target content
- **WHO** (which domain, venture, or context) the contract applies to
- **Acceptable tension range**: The tolerance band within which the system operates normally

A covenant is NOT a "pipeline config" — it is a declaration of intent that bridges the gap between what IS (the anchors Harpoon finds in reality) and what SHOULD BE (the desired pattern state). When tension exceeds the covenant's acceptable range, action is required.

Example: A covenant for EEShow content might specify that `fda_core` critical anchors must be ABSENT (zero tolerance for prohibited health claims), `zone_signals` detect anchors should COVER all four narrative zones (comprehensive storytelling), and `governance` detect anchors should be PRESENT (evidence of policy awareness).

### Strike = Parallel Execution Plan

A **Strike** is a parallel execution plan derived from analyzing covenant gaps across multiple modules. When the Winch measures unacceptable tension across several pattern domains simultaneously, Boris (the orchestrator) assembles a Strike: a set of parallel remediation or analysis tasks that address the gaps concurrently.

Strike planning is Boris's domain — Harpoon provides the anchor data, Winch measures the tension, the Covenant defines the acceptable state, and Boris plans the Strike to close the gap.

## Module Registry: The Pattern Library

The module registry at `compliance-modules/` (path is historical — these are pattern modules, not exclusively compliance modules) serves as Harpoon's pattern library. Each JSON file defines a domain-specific anchor set:

```
compliance-modules/
├── _global/                      # always_on modules (safety floor)
│   └── fda_core.json            # Hard anchors: FDA prohibited terms
├── eesystem/                     # EEShow podcast domain
│   └── fda_extended.json        # Extended health content anchors
├── canon/                        # Canon governance
│   └── governance.json          # Policy pattern anchors (detect tier)
├── narrative/                    # Creative: narrative pattern detection
│   └── zone_signals.json        # Zone-classification signal anchors
└── venture/                      # Per-venture domains
    └── sunlink/
        └── solar_claims.json    # Solar marketing pattern anchors
```

Key properties of the registry:
- **`always_on: true`** modules are compiled into every scan regardless of filters (safety floor)
- **Domain filtering** (`--domain canon`) loads domain-specific modules PLUS all always_on modules
- **Cherry-picking** (`--modules solar_claims,fda_extended`) loads exactly the specified modules
- **Module creation** is as simple as writing a JSON file to the appropriate domain directory
- **Version metadata** is tracked per module but not yet enforced

## Civilization Priors as Pattern Anchors

The priors modules represent a special application of Harpoon's Detect tier. When civilization priors (Aesop's Fables, The Prophet, sonar data, world corpus) are ingested into RuVector, they also define anchor patterns that Harpoon can scan for:

- **Archetypal anchors**: Trickster, fool, king, sage patterns from Aesop
- **Philosophical anchors**: Love, freedom, death, joy themes from The Prophet
- **Historical anchors**: Constitutional language, era-specific terminology from the world corpus
- **Frequency anchors**: Narrative frequency signatures from sonar data

These anchors operate exclusively at the Detect tier — they classify and annotate, never block. Their purpose is to ground system behavior against long-lived narrative invariants: patterns that have persisted across centuries of human storytelling and governance.

## Terminology Correction Table

| Old Term | New Term | Rationale |
|----------|----------|-----------|
| Compliance scanner | Pattern anchor engine | Harpoon is domain-agnostic; compliance is one use case |
| Violation | Anchor / PatternMatch | A match is a fixed coordinate, not inherently a violation |
| Compliance scan | Pattern anchor scan | Scanning locates anchors, not just violations |
| Compliance module | Pattern module | Modules define anchor sets for any domain |
| Guard | Anchor automaton | The compiled automaton anchors against known patterns |
| Pipeline config | Covenant | A reality-to-target contract, not a configuration file |
| Compliance terms | Pattern anchors / anchor terms | Terms are reference coordinates in pattern-space |
| Regulatory detection | Signal classification | Detection classifies signals; regulation is one application |
| Compliance module registry | Pattern module registry | The registry holds pattern libraries, not just compliance rules |
| Drift | Anchor tension | The gap between memory systems, measured as tension |
| Drift companion | Tension companion | Pairing of pattern anchors with ecotone tension state |
| Drift trajectory | Tension trajectory | Directional measure of gap evolution over time |

## Integration with the Manor

Harpoon integrates with the broader operationTorque architecture through several touchpoints:

1. **Boris orchestration**: Boris plans and executes Strikes based on Harpoon's anchor data and Winch tension measurements
2. **Ecotone integrity gate**: Session scans pair pattern anchors with ecotone state to produce arc summaries (RESOLVING, STAGNATING, INSUFFICIENT, SINGULAR)
3. **Bicameral memory**: Anchor tension between FAISS and RuVector mirrors the Winch concept — measuring the gap between two representations of reality
4. **Civilization priors**: The third memory chamber provides long-lived anchors against which current behavior is measured
5. **Venture system**: Each venture can define its own pattern modules, making Harpoon's anchor engine available to any domain the Manor serves

This document supersedes any prior characterization of Harpoon as solely a "compliance" system. Harpoon is a pattern anchor engine. Compliance is one covenant among many.
