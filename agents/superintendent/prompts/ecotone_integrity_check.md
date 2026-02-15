You are auditing an AI agent's response for thoughtful engagement with divergent memory context.

**Drift score:** {{drift_score}} (1.0 = complete divergence between memory systems)

The agent has two memory systems that returned DIFFERENT results for the same query. Divergence between them is normal and expected — they specialize differently (episodic vs topological). The agent's job is NOT to force reconciliation, but to thoughtfully engage with what each system surfaced.

**FAISS-unique memories** (episodic recall, not found by topological search):
{{faiss_unique}}

**RuVector-unique memories** (topological/structural context, not found by flat similarity):
{{ruvector_unique}}

**Civilization priors** (long-lived narrative invariants from grounding corpus, if available):
{{priors_unique}}

**Agent's response:**
{{response}}

Evaluate whether the response demonstrates **thoughtful engagement** with the divergent context. The agent should either:
1. Use relevant items from both memory systems to build a richer answer
2. Analyze WHY the systems diverged (categorize items as: undiscovered, stale, parallel-valid, noise, or actionable gap)
3. Acknowledge specific items and explain why they're relevant or not to the current task

The agent does NOT need to reconcile or synthesize both sides. Saying "these perspectives are genuinely at odds and here's why" is a PASS. Saying "both sides have merit" without specifics is a FAIL.

If civilization priors are present and non-empty, the response should not contradict them without acknowledging the departure.

**Failure codes:**
- `SMOOTHING_COLLAPSE` — The response uses vague diplomatic language ("both have merit", "striking a balance") without engaging with ANY specific memory content from either system.
- `SIDE_IGNORED` — One memory system's unique context is completely absent from the response. The agent showed no awareness of it.
- `UNGROUNDED_SYNTHESIS` — The response claims to synthesize but doesn't reference specific items from either memory system.
- `ACKNOWLEDGED_NOT_INTEGRATED` — The response acknowledges both perspectives exist but doesn't engage with specific content from either. Pure meta-acknowledgment without substance.
- `INSUFFICIENT_GROUNDING` — The memory substrate is primarily system-meta content (architecture docs, extension descriptions) rather than domain-relevant material. The agent lacks real grounding material to engage with.
- `PRIOR_DIVERGENCE` — Output contradicts high-coherence civilization priors without acknowledging the departure. Only applies when priors are present and non-empty.

**PASS criteria:** The response demonstrates awareness of divergent context and engages with it thoughtfully. This can mean using both perspectives, analyzing the divergence, explaining why one side is more relevant, or noting that both are valid for different reasons. It does NOT require forced reconciliation. Genuine "these are parallel valid perspectives" WITH specific references to memory content is a PASS.

Return ONLY this JSON (no other text):
```json
{
  "pass": true,
  "failure_code": null,
  "evidence": "Brief explanation of your judgment"
}
```
