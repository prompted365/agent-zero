# Repo Guidance

The detailed exploration notes and deployment investigation live in
`ROBUST_EXPLORE_JOURNAL_AND_PLAN.md` at the repository root. That file
summarizes the project structure and highlights a docker-compose volume
path issue which can prevent successful container startup.

This monorepo contains:

- **Python core** in `python/` with helpers, tools, and extensions.
- **Prompts and knowledge base** under `prompts/`, `knowledge/`, and `memory/`.
- **Web UI** static files in `webui/`.
- **Docker** build scripts and runtime setup in `docker/`.
- **Documentation** within `docs/` explaining architecture, installation and troubleshooting.

See the journal file for more context and the suggested fix.
