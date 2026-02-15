import subprocess
import os
from python.helpers.tool import Tool, Response


class BorisStrike(Tool):
    """Execute Homeskillet Boris parallel orchestration and Harpoon compliance scans."""

    WORKSPACE = "/workspace/operationTorque"
    HARPOON_CRATE = "/workspace/operationTorque/crates/harpoon"
    BORIS_CRATE = "/workspace/operationTorque/crates/homeskillet_boris"

    @staticmethod
    def _ensure_cargo_in_path():
        """Ensure Rust cargo binary is in PATH for subprocess calls."""
        cargo_bin = os.path.expanduser("~/.cargo/bin")
        current_path = os.environ.get("PATH", "")
        if cargo_bin not in current_path:
            os.environ["PATH"] = f"{cargo_bin}:{current_path}"

    async def execute(self, action="scan", target_path="/workspace/operationTorque/src", **kwargs):
        self._ensure_cargo_in_path()
        try:
            if action == "scan":
                return await self._harpoon_scan(target_path, **kwargs)
            elif action == "module_scan":
                return await self._harpoon_module_scan(target_path, **kwargs)
            elif action == "session_scan":
                return await self._harpoon_session_scan(target_path, **kwargs)
            elif action == "winch":
                return await self._boris_winch(**kwargs)
            elif action == "status":
                return await self._check_status(**kwargs)
            else:
                return Response(
                    message=f"Unknown action: {action}. Use: scan, module_scan, session_scan, winch, status",
                    break_loop=False,
                )
        except Exception as e:
            return Response(message=f"Boris/Harpoon error: {e}", break_loop=False)

    async def _harpoon_scan(self, target_path, **kwargs):
        """Run Harpoon compliance scan on a directory."""
        cmd = [
            "cargo", "run", "--release",
            "--", "scan", "--path", target_path,
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.HARPOON_CRATE,
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

    async def _harpoon_module_scan(self, target_path, **kwargs):
        """Run Harpoon composable module scan."""
        modules_dir = kwargs.get("modules_dir", f"{self.WORKSPACE}/compliance-modules")
        domain = kwargs.get("domain", None)
        module_ids = kwargs.get("modules", None)
        list_modules = kwargs.get("list_modules", False)

        cmd = [
            "cargo", "run", "--release",
            "--", "module-scan",
            "--modules-dir", modules_dir,
        ]

        if list_modules:
            cmd.append("--list-modules")
        else:
            cmd.extend(["--path", target_path])

        if domain:
            cmd.extend(["--domain", domain])
        if module_ids:
            cmd.extend(["--modules", module_ids])

        try:
            result = subprocess.run(
                cmd,
                cwd=self.HARPOON_CRATE,
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout or ""
            errors = result.stderr or ""

            if result.returncode == 0:
                msg = f"Harpoon module scan completed:\n{output}"
                if errors:
                    msg += f"\nLog:\n{errors}"
            elif result.returncode == 2:
                msg = f"CRITICAL VIOLATIONS found:\n{output}\n{errors}"
            else:
                msg = f"Harpoon module scan failed (exit {result.returncode}):\n{output}\n{errors}"

            return Response(message=msg, break_loop=False)
        except subprocess.TimeoutExpired:
            return Response(
                message=f"Harpoon module scan timed out after 120s on {target_path}.",
                break_loop=False,
            )
        except FileNotFoundError:
            return Response(
                message="cargo not found. Install Rust toolchain.",
                break_loop=False,
            )

    async def _harpoon_session_scan(self, target_path, **kwargs):
        """Run Harpoon session scan with drift companion pairing."""
        from datetime import datetime as dt

        modules_dir = kwargs.get("modules_dir", f"{self.WORKSPACE}/compliance-modules")
        domain = kwargs.get("domain", "lifecycle.mogul")
        ecotone_log_dir = kwargs.get("ecotone_log_dir", f"{self.WORKSPACE}/audit-logs/ecotone")
        session_date = kwargs.get("session_date", dt.utcnow().strftime("%Y-%m-%d"))
        output_format = kwargs.get("output", "json")

        cmd = [
            "cargo", "run", "--release",
            "--", "session-scan",
            "--path", target_path,
            "--modules-dir", modules_dir,
            "--ecotone-log-dir", ecotone_log_dir,
            "--session-date", session_date,
            "--output", output_format,
        ]

        if domain:
            cmd.extend(["--domain", domain])

        try:
            result = subprocess.run(
                cmd,
                cwd=self.HARPOON_CRATE,
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout or ""
            errors = result.stderr or ""

            if result.returncode == 0:
                msg = f"Harpoon session scan completed:\n{output}"
                if errors:
                    msg += f"\nLog:\n{errors}"
            elif result.returncode == 2:
                msg = f"CRITICAL VIOLATIONS found in session:\n{output}\n{errors}"
            else:
                msg = f"Harpoon session scan failed (exit {result.returncode}):\n{output}\n{errors}"

            return Response(message=msg, break_loop=False)
        except subprocess.TimeoutExpired:
            return Response(
                message=f"Harpoon session scan timed out after 120s on {target_path}.",
                break_loop=False,
            )
        except FileNotFoundError:
            return Response(
                message="cargo not found. Install Rust toolchain.",
                break_loop=False,
            )

    async def _boris_winch(self, **kwargs):
        """Execute Boris parallel orchestration winch."""
        cmd = [
            "cargo", "run", "--release",
            "--", "winch",
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.BORIS_CRATE,
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
        try:
            result = subprocess.run(
                ["ls", "-la", f"{self.WORKSPACE}/crates/"],
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
