# Cadence Operations — Scheduled Maintenance & Coordination

## How Internal Cadence Works

The cadence orchestrator (`_50_cadence_orchestrator.py`) fires at `monologue_start` on the first iteration of each monologue. It checks time-based triggers and injects `[CADENCE — Scheduled Actions]` directives into your prompt context.

**Key principle:** The extension injects directives — it does NOT execute actions directly. You read the directive, delegate to subordinates via `call_subordinate`, and the confidence gates verify output.

## Triggers

| Trigger | Interval | What To Do |
|---------|----------|------------|
| `health_check` | 60 min | Check all services (RuVector, Crawlset, Redis, Docker). Delegate to subordinate. |
| `memory_consolidation` | 4 hours | Check RuVector collection stats, trigger GNN training if >50 new docs, review graph for orphaned nodes. |
| `compliance_scan` | 8 hours | Run `boris_strike session_scan` on today's ecotone logs. Review arc summary for STAGNATING patterns. |
| `intelligence_check` | 6 hours | Check `crawlset_extract monitors_list` and `analytics_dashboard`. Note stale monitors. |

## State Persistence

Cross-session state is stored at `/workspace/operationTorque/cadence-state/mogul_cadence.json` (on the bind mount, survives container restart). Each trigger records its `last_run` timestamp and ISO string.

Within-session state is also stored in `extras_persistent["cadence_state"]` for quick access.

## Crawlset Monitors

Use `crawlset_extract` with monitor actions to set up external scheduling:

```json
{"action": "monitors_create", "name": "daily-intel-sweep", "url": "https://example.com", "schedule": "0 8 * * *"}
```

Monitors run in the Crawlset pipeline (Celery Beat) independently of your session. Use `monitors_list` to check status, `monitors_trigger` for manual runs, `monitors_runs` for history.

## Coordination Pattern

1. **Internal cadence** (monologue_start) triggers awareness of due tasks
2. **You dispatch** via `call_subordinate` with appropriate profiles
3. **Crawlset monitors** handle background intelligence gathering independently
4. **Ecotone gate** validates subordinate output quality
5. **Cadence state file** tracks what ran and when — prevents double-execution

## Best Practices

- Process cadence directives AFTER handling the user's current request
- Delegate to subordinates — don't do grunt work yourself
- Use FOUNDATIONAL_RIGOR profile for health checks and compliance scans
- Log anomalies only — silence means health
- If a cadence trigger consistently fails, note it in memory for operational plan adjustment
