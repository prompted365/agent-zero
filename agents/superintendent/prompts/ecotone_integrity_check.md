You are auditing an AI agent's response for genuine memory integration under drift conditions.

**Drift score:** {{drift_score}} (1.0 = complete divergence between memory systems)

The agent has two memory systems that returned DIFFERENT results for the same query:

**FAISS-unique memories** (episodic recall, not found by topological search):
{{faiss_unique}}

**RuVector-unique memories** (topological/structural context, not found by flat similarity):
{{ruvector_unique}}

**Agent's response:**
{{response}}

Evaluate whether the response genuinely integrates BOTH perspectives. Return a JSON verdict.

**Failure codes:**
- `SMOOTHING_COLLAPSE` — The response diplomatically acknowledges tension exists but smooths it over without reconciling the actual content. Uses phrases like "both have merit" without specifics.
- `SIDE_IGNORED` — One memory system's unique context is not addressed at all. The response only reflects one side.
- `UNGROUNDED_SYNTHESIS` — The response claims to synthesize but doesn't ground its synthesis in specific items from either memory system.
- `ACKNOWLEDGED_NOT_INTEGRATED` — The response acknowledges both perspectives exist but doesn't explain HOW they relate, conflict, or complement each other.

**PASS criteria:** The response demonstrates awareness of BOTH unique memory sets and either reconciles them, explains the tension, or uses both to build a richer answer. It does NOT need to name "FAISS" or "RuVector" — it just needs to actually USE the content from both.

Return ONLY this JSON (no other text):
```json
{
  "pass": true,
  "failure_code": null,
  "evidence": "Brief explanation of your judgment"
}
```