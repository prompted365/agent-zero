## ingest_corpus_priors

Ingest civilization priors (Aesop's Fables, The Prophet, world corpus) into the `civilization_priors` RuVector collection. These grounding documents feed the tri-cameral drift tracker — they provide long-lived narrative invariants that anchor your reasoning against historical and philosophical precedent.

**Actions:**

### `ingest`
Parse all corpus files from `data/corpus-priors/` and bulk-insert into RuVector:
- **Aesop's Fables** (~300 fables with morals and archetypes)
- **The Prophet** (28 chapters by Kahlil Gibran)
- **Sonar data** (~208 frequency/narrative samples)
- **World corpus** (477 historical documents with temporal/era/keyword indices)

Generates embeddings using the same `all-MiniLM-L6-v2` model as your bicameral memory. Idempotent — safe to re-run (overwrites by document ID).

```json
{
  "tool_name": "ingest_corpus_priors",
  "tool_args": {
    "action": "ingest"
  }
}
```

### `status`
Check collection statistics for `civilization_priors` — document count, dimensionality, storage.

```json
{
  "tool_name": "ingest_corpus_priors",
  "tool_args": {
    "action": "status"
  }
}
```

**When to use:** After first boot, after corpus files are updated, or when drift tracker reports empty priors chamber. The tri-cameral drift tracker (`_55_quiver_drift_tracker`) queries this collection automatically once populated.
