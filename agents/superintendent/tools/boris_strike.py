import subprocess
from python.helpers.tool import Tool, Response


class BorisStrike(Tool):
    """Execute Homeskillet Boris parallel orchestration and EESystem Harpoon compliance scans."""

    async def execute(self, action="scan", target_path="/workspace/operationTorque/src", **kwargs):
        try:
            if action == "scan":
                return await self._harpoon_scan(target_path, **kwargs)
            elif action == "winch":
                return await self._boris_winch(**kwargs)
            elif action == "status":
                return await self._check_status(**kwargs)
            else:
                return Response(
                    message=f"Unknown action: {action}. Use: scan (Harpoon compliance), winch (Boris orchestration), status",
                    break_loop=False,
                )
        except Exception as e:
            return Response(message=f"Boris/Harpoon error: {e}", break_loop=False)

    async def _harpoon_scan(self, target_path, **kwargs):
        """Run EESystem Harpoon compliance scan on a directory."""
        workspace = "/workspace/operationTorque"
        cmd = [
            "cargo", "run", "--release",
            "-p", "eesystem_harpoon",
            "--", "scan", "--path", target_path,
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=f"{workspace}/crates",
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout or ""
            errors = result.stderr or ""

            if result.returncode == 0:
                msg = f"Harpoon scan completed on {target_path}:\n{output}"
                if errors:
                    msg += f"\nWarnings:\n{errors}"
            else:
                msg = f"Harpoon scan failed (exit {result.returncode}):\n{output}\n{errors}"
                # Fallback: try running via workspace root Cargo.toml
                if "no such package" in errors.lower() or "could not find" in errors.lower():
                    msg += f"\n\nNote: Ensure crates/eesystem_harpoon exists. Check with: ls {workspace}/crates/"

            return Response(message=msg, break_loop=False)
        except subprocess.TimeoutExpired:
            return Response(
                message=f"Harpoon scan timed out after 120s on {target_path}. Try a smaller directory.",
                break_loop=False,
            )
        except FileNotFoundError:
            return Response(
                message="cargo not found. Install Rust toolchain: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh",
                break_loop=False,
            )

    async def _boris_winch(self, **kwargs):
        """Execute Boris parallel orchestration winch."""
        workspace = "/workspace/operationTorque"
        cmd = [
            "cargo", "run", "--release",
            "-p", "homeskillet_boris",
            "--", "winch",
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=f"{workspace}/crates",
                capture_output=True,
                text=True,
                timeout=180,
            )
            output = result.stdout or ""
            errors = result.stderr or ""

            if result.returncode == 0:
                msg = f"Boris winch completed:\n{output}"
            else:
                msg = f"Boris winch failed (exit {result.returncode}):\n{output}\n{errors}"

            return Response(message=msg, break_loop=False)
        except subprocess.TimeoutExpired:
            return Response(message="Boris winch timed out after 180s.", break_loop=False)
        except FileNotFoundError:
            return Response(message="cargo not found. Rust toolchain required.", break_loop=False)

    async def _check_status(self, **kwargs):
        """Check if Rust crates are available."""
        workspace = "/workspace/operationTorque"
        try:
            result = subprocess.run(
                ["ls", "-la", f"{workspace}/crates/"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            crates = result.stdout or "No crates directory found."

            # Check cargo availability
            cargo_check = subprocess.run(
                ["cargo", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            cargo = cargo_check.stdout.strip() if cargo_check.returncode == 0 else "cargo not found"

            return Response(
                message=f"Rust toolchain: {cargo}\n\nAvailable crates:\n{crates}",
                break_loop=False,
            )
        except Exception as e:
            return Response(message=f"Status check error: {e}", break_loop=False)
