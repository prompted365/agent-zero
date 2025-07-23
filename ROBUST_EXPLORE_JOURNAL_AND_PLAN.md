# Exploration Journal and Deployment Notes

## Repository Overview

- **Language:** Primarily Python with a small browser UI written in vanilla JS/HTML.
- **Key entry points:** `run_ui.py`, `run_cli.py`, `run_tunnel.py`.
- **Package management:** Python dependencies listed in `requirements.txt` and installed in Docker via `uv pip`.
- **Testing:** pytest suite in `tests/` (currently all tests pass).
- **Docker setup:**
  - Base image and runtime Dockerfiles under `docker/`.
  - `build.sh` builds `agent-zero-run:local` and expects a `BRANCH` build arg.
  - `docker/run/Dockerfile` installs the repo inside `/a0` and runs `initialize.sh` under supervisord.
  - `docker/run/docker-compose.yml` provides a quick start compose file.

## Directory Structure Highlights

- `python/` – core modules (`helpers`, `tools`, `extensions`, `api`).
- `prompts/` – system prompts and templates driving agent behavior.
- `knowledge/` and `memory/` – persistent knowledge base and memory directories.
- `instruments/` – small scripts/functions that can be called as tools.
- `webui/` – static files for the web interface.
- `docs/` – detailed documentation including installation, architecture, and troubleshooting.

## Observed Deployment Mismatch

While reviewing the Docker setup, the compose file under `docker/run/docker-compose.yml` mounts a volume path that does not exist relative to the compose file:

```yaml
services:
  agent-zero:
    container_name: agent-zero
    image: frdel/agent-zero:latest
    volumes:
      - ../..:/a0
    ports:
      - "50080:80"
```

Because the compose file resides in `docker/run`, the relative path `./agent-zero` resolves to `docker/run/agent-zero`, which is not present. This can cause deployment failures when running `docker-compose` because the volume mount cannot be resolved. The project root itself already contains the code, so the volume should likely point one level up (e.g., `..` or `../..`) or reference the current repository root depending on where compose is executed.

## Suggested Fix

Update `docker/run/docker-compose.yml` to reference the correct path to the repository root when mounting `/a0`. For example:

```yaml
    volumes:
      - ../..:/a0
```

assuming the compose file is executed from within `docker/run`. Adjust accordingly if using a different working directory.

## Additional Notes

- The Dockerfile requires the `BRANCH` build argument; missing it will cause the build to abort.
- `build.sh` sets `BRANCH` to `development` by default and runs tests before building.
- All current tests in `tests/` pass, confirming baseline functionality.

