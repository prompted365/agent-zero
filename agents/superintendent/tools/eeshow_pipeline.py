import subprocess
import os
import sqlite3
from python.helpers.tool import Tool, Response


class EeshowPipeline(Tool):
    """Access and manage the EEShow podcast pipeline mounted at /workspace/eeshow-adaptor."""

    EESHOW_DIR = os.environ.get("EESHOW_PIPELINE_DIR", "/workspace/eeshow-adaptor")
    EPISODES_DIR = os.path.join(EESHOW_DIR, "studio/episodes")
    PIPELINE_DB = os.path.join(EESHOW_DIR, "pipeline.db")

    # SQL keywords that indicate a write operation
    WRITE_SQL = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "TRUNCATE"}

    def _safe_path(self, path: str) -> str:
        """Resolve path and verify it stays within EESHOW_DIR. Raises ValueError on traversal."""
        resolved = os.path.realpath(os.path.join(self.EESHOW_DIR, path))
        if not resolved.startswith(os.path.realpath(self.EESHOW_DIR)):
            raise ValueError(f"Path traversal blocked: {path} resolves outside pipeline directory")
        return resolved

    async def execute(self, action="status", **kwargs):
        try:
            if action == "status":
                return await self._status(**kwargs)
            elif action == "list_episodes":
                return await self._list_episodes(**kwargs)
            elif action == "episode_detail":
                return await self._episode_detail(**kwargs)
            elif action == "read_file":
                return await self._read_file(**kwargs)
            elif action == "list_dir":
                return await self._list_dir(**kwargs)
            elif action == "run_script":
                return await self._run_script(**kwargs)
            elif action == "db_query":
                return await self._db_query(**kwargs)
            elif action == "rss_sync":
                return await self._rss_sync(**kwargs)
            elif action == "canonical_build":
                return await self._canonical_build(**kwargs)
            else:
                return Response(
                    message=f"Unknown action: {action}. Use: status, list_episodes, episode_detail, read_file, list_dir, run_script, db_query, rss_sync, canonical_build",
                    break_loop=False,
                )
        except Exception as e:
            return Response(message=f"EEShow pipeline error: {e}", break_loop=False)

    async def _status(self, **kwargs):
        """Check pipeline mount, venv, database, and key directories."""
        checks = []

        # Mount check
        mounted = os.path.isdir(self.EESHOW_DIR)
        checks.append(f"Mount ({self.EESHOW_DIR}): {'OK' if mounted else 'NOT FOUND'}")

        if not mounted:
            return Response(
                message="\n".join(checks) + "\nPipeline not mounted. Check docker-compose volume.",
                break_loop=False,
            )

        # Database check
        db_exists = os.path.isfile(self.PIPELINE_DB)
        checks.append(f"Database (pipeline.db): {'OK' if db_exists else 'NOT FOUND'}")
        if db_exists:
            try:
                conn = sqlite3.connect(self.PIPELINE_DB)
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
                conn.close()
                checks.append(f"  Tables: {', '.join(t[0] for t in tables)}")
            except Exception as e:
                checks.append(f"  DB error: {e}")

        # Key directories
        key_dirs = ["studio/episodes", "tools", "scripts", "transcripts", "narrative", "audio"]
        for d in key_dirs:
            full = os.path.join(self.EESHOW_DIR, d)
            exists = os.path.isdir(full)
            checks.append(f"Dir {d}/: {'OK' if exists else 'MISSING'}")

        # Venv check (won't work in Linux container but note it)
        venv_path = os.path.join(self.EESHOW_DIR, ".venv")
        if os.path.isdir(venv_path):
            checks.append("Venv (.venv): present (macOS — may not work in container, use system python3)")
        else:
            checks.append("Venv (.venv): not found")

        # Python3 availability
        try:
            result = subprocess.run(
                ["python3", "--version"], capture_output=True, text=True, timeout=5
            )
            checks.append(f"Python3: {result.stdout.strip()}")
        except Exception:
            checks.append("Python3: not available")

        return Response(message="\n".join(checks), break_loop=False)

    async def _list_episodes(self, **kwargs):
        """List episode directories in studio/episodes/."""
        if not os.path.isdir(self.EPISODES_DIR):
            return Response(
                message=f"Episodes directory not found: {self.EPISODES_DIR}",
                break_loop=False,
            )

        entries = sorted(os.listdir(self.EPISODES_DIR))
        dirs = [e for e in entries if os.path.isdir(os.path.join(self.EPISODES_DIR, e))]

        if not dirs:
            return Response(message="No episode directories found.", break_loop=False)

        lines = [f"Episodes ({len(dirs)} total):"]
        for d in dirs:
            ep_path = os.path.join(self.EPISODES_DIR, d)
            file_count = sum(1 for _ in os.scandir(ep_path) if _.is_file())
            lines.append(f"  {d}/ ({file_count} files)")

        return Response(message="\n".join(lines), break_loop=False)

    async def _episode_detail(self, episode="", **kwargs):
        """Recursive file listing for a specific episode directory."""
        if not episode:
            return Response(
                message="Provide episode= parameter (e.g., episode='ep-21')",
                break_loop=False,
            )

        ep_path = self._safe_path(f"studio/episodes/{episode}")
        if not os.path.isdir(ep_path):
            return Response(message=f"Episode not found: {ep_path}", break_loop=False)

        lines = [f"Episode: {episode}"]
        for root, dirs, files in os.walk(ep_path):
            level = root.replace(ep_path, "").count(os.sep)
            indent = "  " * (level + 1)
            lines.append(f"{indent}{os.path.basename(root)}/")
            sub_indent = "  " * (level + 2)
            for f in sorted(files):
                fpath = os.path.join(root, f)
                size = os.path.getsize(fpath)
                if size > 1048576:
                    size_str = f"{size / 1048576:.1f}MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.1f}KB"
                else:
                    size_str = f"{size}B"
                lines.append(f"{sub_indent}{f} ({size_str})")

        return Response(message="\n".join(lines), break_loop=False)

    async def _read_file(self, path="", max_lines=200, **kwargs):
        """Read a file from the pipeline directory (path-traversal protected)."""
        if not path:
            return Response(
                message="Provide path= parameter (relative to pipeline root)",
                break_loop=False,
            )

        resolved = self._safe_path(path)
        if not os.path.isfile(resolved):
            return Response(message=f"File not found: {path}", break_loop=False)

        try:
            with open(resolved, "r", errors="replace") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"\n... truncated at {max_lines} lines ...")
                        break
                    lines.append(line.rstrip())
            return Response(message="\n".join(lines), break_loop=False)
        except Exception as e:
            return Response(message=f"Read error: {e}", break_loop=False)

    async def _list_dir(self, path="", **kwargs):
        """List directory contents (path-traversal protected)."""
        resolved = self._safe_path(path) if path else os.path.realpath(self.EESHOW_DIR)

        if not os.path.isdir(resolved):
            return Response(message=f"Directory not found: {path or '/'}", break_loop=False)

        entries = sorted(os.listdir(resolved))
        lines = [f"Contents of {path or '/'}:"]
        for e in entries:
            full = os.path.join(resolved, e)
            if os.path.isdir(full):
                lines.append(f"  {e}/")
            else:
                size = os.path.getsize(full)
                if size > 1048576:
                    size_str = f"{size / 1048576:.1f}MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.1f}KB"
                else:
                    size_str = f"{size}B"
                lines.append(f"  {e} ({size_str})")

        return Response(message="\n".join(lines), break_loop=False)

    async def _run_script(self, script="", args="", timeout=600, **kwargs):
        """Execute a .py or .sh script from within the pipeline directory."""
        if not script:
            return Response(
                message="Provide script= parameter (relative path to .py or .sh file)",
                break_loop=False,
            )

        resolved = self._safe_path(script)
        if not os.path.isfile(resolved):
            return Response(message=f"Script not found: {script}", break_loop=False)

        if not (resolved.endswith(".py") or resolved.endswith(".sh")):
            return Response(
                message=f"Only .py and .sh scripts allowed. Got: {script}",
                break_loop=False,
            )

        # Build command
        if resolved.endswith(".py"):
            cmd = ["python3", resolved]
        else:
            cmd = ["bash", resolved]

        if args:
            cmd.extend(args.split())

        try:
            result = subprocess.run(
                cmd,
                cwd=self.EESHOW_DIR,
                capture_output=True,
                text=True,
                timeout=min(timeout, 600),
            )
            output = result.stdout or ""
            errors = result.stderr or ""

            # Truncate long output
            if len(output) > 10000:
                output = output[:10000] + "\n... output truncated ..."

            if result.returncode == 0:
                msg = f"Script completed (exit 0):\n{output}"
                if errors:
                    msg += f"\nStderr:\n{errors[:3000]}"
            else:
                msg = f"Script failed (exit {result.returncode}):\n{output}\nStderr:\n{errors[:3000]}"

            return Response(message=msg, break_loop=False)
        except subprocess.TimeoutExpired:
            return Response(
                message=f"Script timed out after {timeout}s: {script}",
                break_loop=False,
            )

    async def _db_query(self, sql="", **kwargs):
        """Execute a read-only SQL query against pipeline.db."""
        if not sql:
            return Response(
                message="Provide sql= parameter with a SELECT query",
                break_loop=False,
            )

        # Block write operations
        sql_upper = sql.strip().upper()
        first_word = sql_upper.split()[0] if sql_upper.split() else ""
        if first_word in self.WRITE_SQL:
            return Response(
                message=f"Write operations blocked. Only SELECT queries allowed. Got: {first_word}",
                break_loop=False,
            )

        if not os.path.isfile(self.PIPELINE_DB):
            return Response(message=f"Database not found: {self.PIPELINE_DB}", break_loop=False)

        try:
            conn = sqlite3.connect(self.PIPELINE_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            rows = cursor.fetchmany(100)

            if not rows:
                conn.close()
                return Response(message="Query returned 0 rows.", break_loop=False)

            columns = rows[0].keys()
            lines = [" | ".join(columns)]
            lines.append("-" * len(lines[0]))

            for row in rows:
                lines.append(" | ".join(str(row[c]) for c in columns))

            total = len(rows)
            if total == 100:
                lines.append("... limited to 100 rows ...")

            conn.close()
            return Response(message="\n".join(lines), break_loop=False)
        except Exception as e:
            return Response(message=f"DB query error: {e}", break_loop=False)

    async def _rss_sync(self, **kwargs):
        """Trigger RSS feed import from Transistor FM."""
        rss_script = os.path.join(self.EESHOW_DIR, "scripts", "rss_import.py")
        if not os.path.isfile(rss_script):
            # Try alternate locations
            for alt in ["tools/rss_import.py", "rss_feed_import.py"]:
                alt_path = os.path.join(self.EESHOW_DIR, alt)
                if os.path.isfile(alt_path):
                    rss_script = alt_path
                    break
            else:
                return Response(
                    message="RSS import script not found. Checked: scripts/rss_import.py, tools/rss_import.py, rss_feed_import.py",
                    break_loop=False,
                )

        try:
            result = subprocess.run(
                ["python3", rss_script],
                cwd=self.EESHOW_DIR,
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout or ""
            errors = result.stderr or ""

            if result.returncode == 0:
                msg = f"RSS sync completed:\n{output}"
            else:
                msg = f"RSS sync failed (exit {result.returncode}):\n{output}\n{errors}"

            return Response(message=msg, break_loop=False)
        except subprocess.TimeoutExpired:
            return Response(message="RSS sync timed out after 120s.", break_loop=False)

    async def _canonical_build(self, episode="", **kwargs):
        """Run 9-step narrative verification for an episode."""
        if not episode:
            return Response(
                message="Provide episode= parameter (e.g., episode='ep-21')",
                break_loop=False,
            )

        # Look for the canonical build script
        build_script = None
        for candidate in [
            "scripts/canonical_build.py",
            "tools/canonical_build.py",
            "scripts/process_episode.py",
            "pipeline-cli/canonical_build.py",
        ]:
            path = os.path.join(self.EESHOW_DIR, candidate)
            if os.path.isfile(path):
                build_script = path
                break

        if not build_script:
            return Response(
                message="Canonical build script not found. Checked: scripts/canonical_build.py, tools/canonical_build.py, scripts/process_episode.py, pipeline-cli/canonical_build.py",
                break_loop=False,
            )

        try:
            result = subprocess.run(
                ["python3", build_script, episode],
                cwd=self.EESHOW_DIR,
                capture_output=True,
                text=True,
                timeout=600,
            )
            output = result.stdout or ""
            errors = result.stderr or ""

            if len(output) > 10000:
                output = output[:10000] + "\n... output truncated ..."

            if result.returncode == 0:
                msg = f"Canonical build for {episode} completed:\n{output}"
            else:
                msg = f"Canonical build for {episode} failed (exit {result.returncode}):\n{output}\nStderr:\n{errors[:3000]}"

            return Response(message=msg, break_loop=False)
        except subprocess.TimeoutExpired:
            return Response(
                message=f"Canonical build timed out after 600s for {episode}.",
                break_loop=False,
            )
