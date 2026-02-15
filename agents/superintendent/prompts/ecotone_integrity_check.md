You are auditing an AI agent's response for genuine memory integration under drift conditions.

**Drift score:** {{drift_score}} (1.0 = complete divergence between memory systems)

The agent has two memory systems that returned DIFFERENT results for the same query:

**FAISS-unique memories** (episodic recall, not found by topological search):
{{faiss_unique}}

**RuVector-unique memories** (topological/structural context, not found by flat similarity):
{{ruvector_unique}}

**Civilization priors** (long-lived narrative invariants from grounding corpus, if available):
{{priors_unique}}

**Agent's response:**
{{response}}

Evaluate whether the response genuinely integrates BOTH memory perspectives. If civilization priors are present and non-empty, also evaluate whether the response respected or acknowledged those prior constraints. Return a JSON verdict.

**Failure codes:**
- `SMOOTHING_COLLAPSE` — The response diplomatically acknowledges tension exists but smooths it over without reconciling the actual content. Uses phrases like "both have merit" without specifics.
- `SIDE_IGNORED` — One memory system's unique context is not addressed at all. The response only reflects one side.
- `UNGROUNDED_SYNTHESIS` — The response claims to synthesize but doesn't ground its synthesis in specific items from either memory system.
- `ACKNOWLEDGED_NOT_INTEGRATED` — The response acknowledges both perspectives exist but doesn't explain HOW they relate, conflict, or complement each other.
- `INSUFFICIENT_GROUNDING` — The memory substrate is primarily system-meta content (architecture docs, extension descriptions) rather than domain-relevant material. The agent lacks real grounding material to integrate.
- `PRIOR_DIVERGENCE` — Output violates high-coherence civilization priors (Aesop morals, Prophet teachings, historical precedent) under a meaning-defense lineage without acknowledging the tension. Only applies when priors are present and non-empty.

**PASS criteria:** The response demonstrates awareness of BOTH unique memory sets and either reconciles them, explains the tension, or uses both to build a richer answer. It does NOT need to name "FAISS" or "RuVector" — it just needs to actually USE the content from both. When civilization priors are available, the response should not contradict them without explicitly acknowledging the departure.

Return ONLY this JSON (no other text):
```json
{
  "pass": true,
  "failure_code": null,
  "evidence": "Brief explanation of your judgment"
}
```
