import asyncio
from dataclasses import dataclass
from datetime import datetime
import shlex
import time
from python.helpers.tool import Tool, Response
from python.helpers import files, rfc_exchange, projects, runtime, settings
from python.helpers.print_style import PrintStyle
from python.helpers.shell_local import LocalInteractiveSession
from python.helpers.shell_ssh import SSHInteractiveSession
from python.helpers.docker import DockerContainerManager
from python.helpers.strings import truncate_text as truncate_text_string
from python.helpers.messages import truncate_text as truncate_text_agent
import os
import re
import sys

# Epistemic Compression Gate — Nano-UCoin tool execution economics
GENESIS_GRANT = 2_000_000  # 2M nUC — Phase 0 subsidized physics
BASE_FEE = 10              # nUC per tool execution

# Motivation Layer — PRESTIGE band detection for external distribution
# Physics enforcement: detect commands that publish/distribute externally.
# Internal creation = COGNITIVE (allowed). External distribution = PRESTIGE (blocked).
PRESTIGE_DISTRIBUTION_PATTERNS = [
    re.compile(r"curl\s+.*(?:-X\s*POST|-d\s).*(?:api\.twitter|api\.x\.com|medium\.com/p|api\.linkedin|mastodon|bluesky|substack)", re.IGNORECASE),
    re.compile(r"(?:twurl|toot|tweet)\s+", re.IGNORECASE),
    re.compile(r"(?:publish|broadcast|announce)\s+.*(?:blog|post|article|thread|tweet)", re.IGNORECASE),
    re.compile(r"gh\s+release\s+create", re.IGNORECASE),
]

# --- Intent Gate: content-aware PRESTIGE detection (Bridge 2 physics) ---
# Lazy-loaded NaiveSurveillance singleton for classify_intent().
# Complements PRESTIGE_DISTRIBUTION_PATTERNS (which catch specific commands)
# by analyzing code CONTENT for prestige pursuit + publication intent.
_intent_gate_surveillance = None
_intent_gate_init_attempted = False


def _get_intent_gate():
    """Lazy-init NaiveSurveillance for intent gate. Returns None on failure."""
    global _intent_gate_surveillance, _intent_gate_init_attempted
    if _intent_gate_init_attempted:
        return _intent_gate_surveillance
    _intent_gate_init_attempted = True
    try:
        workspace = os.environ.get("WORKSPACE_DIR", "/workspace/operationTorque")
        fc_src = os.path.join(workspace, "fusion_core_repo", "src")
        if fc_src not in sys.path:
            sys.path.insert(0, fc_src)
        from fusion_core.naive_surveillance import NaiveSurveillance
        shapes_path = os.path.join(workspace, "compliance-modules", "archetype_shapes.json")
        _intent_gate_surveillance = NaiveSurveillance(shapes_path=shapes_path)
    except Exception:
        _intent_gate_surveillance = None
    return _intent_gate_surveillance

# Timeouts for python, nodejs, and terminal runtimes.
CODE_EXEC_TIMEOUTS: dict[str, int] = {
    "first_output_timeout": 30,
    "between_output_timeout": 15,
    "max_exec_timeout": 180,
    "dialog_timeout": 5,
}

# Timeouts for output runtime.
OUTPUT_TIMEOUTS: dict[str, int] = {
    "first_output_timeout": 90,
    "between_output_timeout": 45,
    "max_exec_timeout": 300,
    "dialog_timeout": 5,
}

@dataclass
class ShellWrap:
    id: int
    session: LocalInteractiveSession | SSHInteractiveSession
    running: bool

@dataclass
class State:
    ssh_enabled: bool
    shells: dict[int, ShellWrap]


class CodeExecution(Tool):

    # Common shell prompt regex patterns (add more as needed)
    prompt_patterns = [
        re.compile(r"\\(venv\\).+[$#] ?$"),  # (venv) ...$ or (venv) ...#
        re.compile(r"root@[^:]+:[^#]+# ?$"),  # root@container:~#
        re.compile(r"[a-zA-Z0-9_.-]+@[^:]+:[^$#]+[$#] ?$"),  # user@host:~$
        re.compile(r"\(?.*\)?\s*PS\s+[^>]+> ?$"),  # PowerShell prompt like (base) PS C:\...>
    ]
    # potential dialog detection
    dialog_patterns = [
        re.compile(r"Y/N", re.IGNORECASE),  # Y/N anywhere in line
        re.compile(r"yes/no", re.IGNORECASE),  # yes/no anywhere in line
        re.compile(r":\s*$"),  # line ending with colon
        re.compile(r"\?\s*$"),  # line ending with question mark
    ]

    async def execute(self, **kwargs) -> Response:

        await self.agent.handle_intervention()  # wait for intervention and handle it, if paused

        # --- Epistemic Compression Gate: Pre-exec balance check ---
        balance = self.agent.context.get_data("ucoin_balance")
        if balance is None:
            balance = GENESIS_GRANT
            self.agent.context.set_data("ucoin_balance", balance)

        if balance < BASE_FEE:
            return Response(
                message=(
                    f"[ECONOMY_HALT: FUNDS_EXHAUSTED] Tool execution denied. "
                    f"Required: {BASE_FEE} nUC. Available: {balance} nUC. "
                    "Ask operator to top up ucoin_balance."
                ),
                break_loop=False,
            )
        # --- End pre-exec gate ---

        # --- Motivation Layer: PRESTIGE band detection ---
        code = self.args.get("code", "")
        for pat in PRESTIGE_DISTRIBUTION_PATTERNS:
            if pat.search(code):
                self.agent.context.set_data("motivation_flag", "PRESTIGE")
                self.agent.context.set_data(
                    "motivation_flag_source",
                    f"code_execution_tool:{code[:100]}",
                )
                return Response(
                    message=(
                        f"[MOTIVATION_GATE: PRESTIGE_BLOCKED] External distribution "
                        f"command detected. Internal creation is allowed (COGNITIVE band), "
                        f"but publishing/broadcasting to external audiences is blocked "
                        f"(PRESTIGE band). If this is a legitimate COGNITIVE operation, "
                        f"rephrase the command to avoid external distribution patterns."
                    ),
                    break_loop=False,
                )

        # --- Publication Vector Gate v2: surveillance-aware intent detection ---
        # The drift tracker (prompt-time) runs observe() on the user message and
        # stores the snapshot in AgentContext.data. We read it here so the physics
        # gate sees what surveillance already detected — no redundant decomposition,
        # shared state between prompt-time observation and execution-time enforcement.
        #
        # Publication vector is the DOMINANT classifier. When detected, the teeth
        # (prestige/extraction archetypes) determine the band. Certain bands don't
        # pass. The business case alongside does NOT override the band.
        gate = _get_intent_gate()
        if gate is not None:
            try:
                # Read surveillance snapshot from drift tracker (prompt-time)
                surveillance_snapshot = self.agent.context.get_data("_surveillance_snapshot")

                # Get user message from surveillance snapshot (drift tracker stored it)
                # or fall back to extracting from conversation history
                user_msg = ""
                if surveillance_snapshot:
                    user_msg = surveillance_snapshot.get("user_message", "")
                if not user_msg:
                    try:
                        msgs = getattr(self.agent.history, "messages", [])
                        for msg in reversed(msgs):
                            role = getattr(msg, "role", "")
                            if role == "user":
                                content = getattr(msg, "content", "") or ""
                                user_msg = content[:2000]
                                break
                    except Exception:
                        pass

                intent = gate.classify_vector(
                    user_message=user_msg,
                    tool_code=code,
                    action_type="code_execution",
                    surveillance_snapshot=surveillance_snapshot,
                )
                if intent.blocked:
                    self.agent.context.set_data("motivation_flag", "PRESTIGE")
                    self.agent.context.set_data(
                        "motivation_flag_source",
                        f"vector_gate:{intent.reason[:200]}",
                    )
                    return Response(
                        message=(
                            f"[MOTIVATION_GATE: VECTOR_BLOCKED] {intent.reason} "
                            f"Band: {intent.motivation_band}. "
                            f"Internal analysis and discussion of these patterns is "
                            f"allowed (COGNITIVE). Creating deliverables that ride "
                            f"a publication vector with banned-band teeth is blocked "
                            f"at the physics layer."
                        ),
                        break_loop=False,
                    )

                # Burn pressure: store multiplier for post-exec cost calculation
                if intent.burn_multiplier > 1.0:
                    self.agent.context.set_data(
                        "_motivation_burn_multiplier", intent.burn_multiplier,
                    )
            except Exception:
                pass  # Graceful degradation — regex gate above still protects
        # --- End motivation gate ---

        runtime = self.args.get("runtime", "").lower().strip()
        session = int(self.args.get("session", 0))
        self.allow_running = bool(self.args.get("allow_running", False))
        reset = bool(self.args.get("reset", False) or runtime == "reset")

        if runtime == "python":
            response = await self.execute_python_code(
                code=self.args["code"], session=session, reset=reset
            )
        elif runtime == "nodejs":
            response = await self.execute_nodejs_code(
                code=self.args["code"], session=session, reset=reset
            )
        elif runtime == "terminal":
            response = await self.execute_terminal_command(
                command=self.args["code"], session=session, reset=reset
            )
        elif runtime == "output":
            response = await self.get_terminal_output(
                session=session, timeouts=OUTPUT_TIMEOUTS
            )
        elif runtime == "reset":
            response = await self.reset_terminal(session=session)
        else:
            response = self.agent.read_prompt(
                "fw.code.runtime_wrong.md", runtime=runtime
            )

        if not response:
            response = self.agent.read_prompt(
                "fw.code.info.md", info=self.agent.read_prompt("fw.code.no_output.md")
            )

        # --- Epistemic Compression Gate: Post-exec cost math ---
        raw_output_chars = len(response)
        context_tax = raw_output_chars // 100
        base_cost = BASE_FEE + context_tax

        # Burn pressure: motivation-aware cost multiplier
        # Maps to Nautilus Swarm burn channels: gap_burn (claimed vs detected
        # motivation), demurrage (sustained patterns), agent_penalty (teeth on
        # publication vectors). Applied by classify_vector() pre-exec.
        burn_mult = self.agent.context.get_data("_motivation_burn_multiplier") or 1.0
        cost = int(base_cost * burn_mult)
        if burn_mult > 1.0:
            self.agent.context.set_data("_motivation_burn_multiplier", 1.0)  # Reset after use

        balance = self.agent.context.get_data("ucoin_balance")
        if balance is None:
            balance = GENESIS_GRANT
        balance -= cost
        self.agent.context.set_data("ucoin_balance", balance)

        self.agent.context.set_data(
            "tool_spent_total_nuc",
            (self.agent.context.get_data("tool_spent_total_nuc") or 0) + cost,
        )
        self.agent.context.set_data(
            "tool_calls_total",
            (self.agent.context.get_data("tool_calls_total") or 0) + 1,
        )
        self.agent.context.set_data(
            "tool_output_chars_total",
            (self.agent.context.get_data("tool_output_chars_total") or 0) + raw_output_chars,
        )

        tool_costs = self.agent.context.get_data("tool_costs") or []
        tool_costs.append({
            "tool_name": self.name,
            "raw_chars": raw_output_chars,
            "cost_nano": cost,
            "balance_after": balance,
            "timestamp": datetime.now().isoformat(),
        })
        if len(tool_costs) > 20:
            tool_costs = tool_costs[-20:]
        self.agent.context.set_data("tool_costs", tool_costs)

        # Prepend metabolic metadata for compression gate
        response = f"__METABOLIC_DATA__:{raw_output_chars}|{cost}|{balance}\n{response}"
        # --- End post-exec cost math ---

        return Response(message=response, break_loop=False)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="code_exe",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
        )

    def get_heading(self, text: str = ""):
        if not text:
            text = f"{self.name} - {self.args['runtime'] if 'runtime' in self.args else 'unknown'}"
        # text = truncate_text_string(text, 60) # don't truncate here, log.py takes care of it
        session = self.args.get("session", None)
        session_text = f"[{session}] " if session or session == 0 else ""
        return f"icon://terminal {session_text}{text}"

    async def after_execution(self, response, **kwargs):
        self.agent.hist_add_tool_result(self.name, response.message, **(response.additional or {}))

    async def prepare_state(self, reset=False, session: int | None = None):
        self.state: State | None = self.agent.get_data("_cet_state")
        # always reset state when ssh_enabled changes
        if not self.state or self.state.ssh_enabled != self.agent.config.code_exec_ssh_enabled:
            # initialize shells dictionary if not exists
            shells: dict[int, ShellWrap] = {}
        else:
            shells = self.state.shells.copy()

        # Only reset the specified session if provided
        if reset and session is not None and session in shells:
            await shells[session].session.close()
            del shells[session]
        elif reset and not session:
            # Close all sessions if full reset requested
            for s in list(shells.keys()):
                await shells[s].session.close()
            shells = {}

        # initialize local or remote interactive shell interface for session 0 if needed
        if session is not None and session not in shells:
            cwd = await self.ensure_cwd()
            if self.agent.config.code_exec_ssh_enabled:
                pswd = (
                    self.agent.config.code_exec_ssh_pass
                    if self.agent.config.code_exec_ssh_pass
                    else await rfc_exchange.get_root_password()
                )
                shell = SSHInteractiveSession(
                    self.agent.context.log,
                    self.agent.config.code_exec_ssh_addr,
                    self.agent.config.code_exec_ssh_port,
                    self.agent.config.code_exec_ssh_user,
                    pswd,
                    cwd=cwd,
                )
            else:
                shell = LocalInteractiveSession(cwd=cwd)

            shells[session] = ShellWrap(id=session, session=shell, running=False)
            await shell.connect()

        self.state = State(shells=shells, ssh_enabled=self.agent.config.code_exec_ssh_enabled)
        self.agent.set_data("_cet_state", self.state)
        return self.state

    async def execute_python_code(self, session: int, code: str, reset: bool = False):
        escaped_code = shlex.quote(code)
        command = f"ipython -c {escaped_code}"
        prefix = "python> " + self.format_command_for_output(code) + "\n\n"
        return await self.terminal_session(session, command, reset, prefix)

    async def execute_nodejs_code(self, session: int, code: str, reset: bool = False):
        escaped_code = shlex.quote(code)
        command = f"node /exe/node_eval.js {escaped_code}"
        prefix = "node> " + self.format_command_for_output(code) + "\n\n"
        return await self.terminal_session(session, command, reset, prefix)

    async def execute_terminal_command(
        self, session: int, command: str, reset: bool = False
    ):
        prefix = ("bash>" if not runtime.is_windows() or self.agent.config.code_exec_ssh_enabled else "PS>") + self.format_command_for_output(command) + "\n\n"
        return await self.terminal_session(session, command, reset, prefix)

    async def terminal_session(
        self, session: int, command: str, reset: bool = False, prefix: str = "", timeouts: dict | None = None
    ):

        self.state = await self.prepare_state(reset=reset, session=session)

        await self.agent.handle_intervention()  # wait for intervention and handle it, if paused

        # Check if session is running and handle it
        if not self.allow_running:
            if response := await self.handle_running_session(session):
                return response
        
        # try again on lost connection
        for i in range(2):
            try:

                self.state.shells[session].running = True
                await self.state.shells[session].session.send_command(command)

                locl = (
                    " (local)"
                    if isinstance(self.state.shells[session].session, LocalInteractiveSession)
                    else (
                        " (remote)"
                        if isinstance(self.state.shells[session].session, SSHInteractiveSession)
                        else " (unknown)"
                    )
                )

                PrintStyle(
                    background_color="white", font_color="#1B4F72", bold=True
                ).print(f"{self.agent.agent_name} code execution output{locl}")
                return await self.get_terminal_output(session=session, prefix=prefix, timeouts=(timeouts or CODE_EXEC_TIMEOUTS))

            except Exception as e:
                if i == 1:
                    # try again on lost connection
                    PrintStyle.error(str(e))
                    await self.prepare_state(reset=True, session=session)
                    continue
                else:
                    raise e

    def format_command_for_output(self, command: str):
        # truncate long commands
        short_cmd = command[:200]
        # normalize whitespace for cleaner output
        short_cmd = " ".join(short_cmd.split())
        # replace any sequence of ', ", or ` with a single '
        # short_cmd = re.sub(r"['\"`]+", "'", short_cmd) # no need anymore
        # final length
        short_cmd = truncate_text_string(short_cmd, 100)
        return f"{short_cmd}"

    async def get_terminal_output(
        self,
        session=0,
        reset_full_output=True,
        first_output_timeout=30,  # Wait up to x seconds for first output
        between_output_timeout=15,  # Wait up to x seconds between outputs
        dialog_timeout=5,  # potential dialog detection timeout
        max_exec_timeout=180,  # hard cap on total runtime
        sleep_time=0.1,
        prefix="",
        timeouts: dict | None = None,
    ):

        # if not self.state:
        self.state = await self.prepare_state(session=session)

        # Override timeouts if a dict is provided
        if timeouts:
            first_output_timeout = timeouts.get("first_output_timeout", first_output_timeout)
            between_output_timeout = timeouts.get("between_output_timeout", between_output_timeout)
            dialog_timeout = timeouts.get("dialog_timeout", dialog_timeout)
            max_exec_timeout = timeouts.get("max_exec_timeout", max_exec_timeout)

        start_time = time.time()
        last_output_time = start_time
        full_output = ""
        truncated_output = ""
        got_output = False

        # if prefix, log right away
        if prefix:
            self.log.update(content=prefix)

        while True:
            await asyncio.sleep(sleep_time)
            full_output, partial_output = await self.state.shells[session].session.read_output(
                timeout=1, reset_full_output=reset_full_output
            )
            reset_full_output = False  # only reset once

            await self.agent.handle_intervention()

            now = time.time()
            if partial_output:
                PrintStyle(font_color="#85C1E9").stream(partial_output)
                # full_output += partial_output # Append new output
                truncated_output = self.fix_full_output(full_output)
                self.set_progress(truncated_output)
                heading = self.get_heading_from_output(truncated_output, 0)
                self.log.update(content=prefix + truncated_output, heading=heading)
                last_output_time = now
                got_output = True

                # Check for shell prompt at the end of output
                last_lines = (
                    truncated_output.splitlines()[-3:] if truncated_output else []
                )
                last_lines.reverse()
                for idx, line in enumerate(last_lines):
                    for pat in self.prompt_patterns:
                        if pat.search(line.strip()):
                            PrintStyle.info(
                                "Detected shell prompt, returning output early."
                            )
                            last_lines.reverse()
                            heading = self.get_heading_from_output(
                                "\n".join(last_lines), idx + 1, True
                            )
                            self.log.update(heading=heading)
                            self.mark_session_idle(session)
                            return truncated_output

            # Check for max execution time
            if now - start_time > max_exec_timeout:
                sysinfo = self.agent.read_prompt(
                    "fw.code.max_time.md", timeout=max_exec_timeout
                )
                response = self.agent.read_prompt("fw.code.info.md", info=sysinfo)
                if truncated_output:
                    response = truncated_output + "\n\n" + response
                PrintStyle.warning(sysinfo)
                heading = self.get_heading_from_output(truncated_output, 0)
                self.log.update(content=prefix + response, heading=heading)
                return response

            # Waiting for first output
            if not got_output:
                if now - start_time > first_output_timeout:
                    sysinfo = self.agent.read_prompt(
                        "fw.code.no_out_time.md", timeout=first_output_timeout
                    )
                    response = self.agent.read_prompt("fw.code.info.md", info=sysinfo)
                    PrintStyle.warning(sysinfo)
                    self.log.update(content=prefix + response)
                    return response
            else:
                # Waiting for more output after first output
                if now - last_output_time > between_output_timeout:
                    sysinfo = self.agent.read_prompt(
                        "fw.code.pause_time.md", timeout=between_output_timeout
                    )
                    response = self.agent.read_prompt("fw.code.info.md", info=sysinfo)
                    if truncated_output:
                        response = truncated_output + "\n\n" + response
                    PrintStyle.warning(sysinfo)
                    heading = self.get_heading_from_output(truncated_output, 0)
                    self.log.update(content=prefix + response, heading=heading)
                    return response

                # potential dialog detection
                if now - last_output_time > dialog_timeout:
                    # Check for dialog prompt at the end of output
                    last_lines = (
                        truncated_output.splitlines()[-2:] if truncated_output else []
                    )
                    for line in last_lines:
                        for pat in self.dialog_patterns:
                            if pat.search(line.strip()):
                                PrintStyle.info(
                                    "Detected dialog prompt, returning output early."
                                )

                                sysinfo = self.agent.read_prompt(
                                    "fw.code.pause_dialog.md", timeout=dialog_timeout
                                )
                                response = self.agent.read_prompt(
                                    "fw.code.info.md", info=sysinfo
                                )
                                if truncated_output:
                                    response = truncated_output + "\n\n" + response
                                PrintStyle.warning(sysinfo)
                                heading = self.get_heading_from_output(
                                    truncated_output, 0
                                )
                                self.log.update(
                                    content=prefix + response, heading=heading
                                )
                                return response

    async def handle_running_session(
        self,
        session=0,
        reset_full_output=True, 
        prefix=""
    ):
        if not self.state or session not in self.state.shells:
            return None
        if not self.state.shells[session].running:
            return None
        
        full_output, _ = await self.state.shells[session].session.read_output(
            timeout=1, reset_full_output=reset_full_output
        )
        truncated_output = self.fix_full_output(full_output)
        self.set_progress(truncated_output)
        heading = self.get_heading_from_output(truncated_output, 0)

        last_lines = (
            truncated_output.splitlines()[-3:] if truncated_output else []
        )
        last_lines.reverse()
        for idx, line in enumerate(last_lines):
            for pat in self.prompt_patterns:
                if pat.search(line.strip()):
                    PrintStyle.info(
                        "Detected shell prompt, returning output early."
                    )
                    self.mark_session_idle(session)
                    return None

        has_dialog = False 
        for line in last_lines:
            for pat in self.dialog_patterns:
                if pat.search(line.strip()):
                    has_dialog = True
                    break
            if has_dialog:
                break

        if has_dialog:
            sys_info = self.agent.read_prompt("fw.code.pause_dialog.md", timeout=1)       
        else:
            sys_info = self.agent.read_prompt("fw.code.running.md", session=session)

        response = self.agent.read_prompt("fw.code.info.md", info=sys_info)
        if truncated_output:
            response = truncated_output + "\n\n" + response
        PrintStyle(font_color="#FFA500", bold=True).print(response)
        self.log.update(content=prefix + response, heading=heading)
        return response
    
    def mark_session_idle(self, session: int = 0):
        # Mark session as idle - command finished
        if self.state and session in self.state.shells:
            self.state.shells[session].running = False

    async def reset_terminal(self, session=0, reason: str | None = None):
        # Print the reason for the reset to the console if provided
        if reason:
            PrintStyle(font_color="#FFA500", bold=True).print(
                f"Resetting terminal session {session}... Reason: {reason}"
            )
        else:
            PrintStyle(font_color="#FFA500", bold=True).print(
                f"Resetting terminal session {session}..."
            )

        # Only reset the specified session while preserving others
        await self.prepare_state(reset=True, session=session)
        response = self.agent.read_prompt(
            "fw.code.info.md", info=self.agent.read_prompt("fw.code.reset.md")
        )
        self.log.update(content=response)
        return response

    def get_heading_from_output(self, output: str, skip_lines=0, done=False):
        done_icon = " icon://done_all" if done else ""

        if not output:
            return self.get_heading() + done_icon

        # find last non-empty line with skip
        lines = output.splitlines()
        # Start from len(lines) - skip_lines - 1 down to 0
        for i in range(len(lines) - skip_lines - 1, -1, -1):
            line = lines[i].strip()
            if not line:
                continue
            return self.get_heading(line) + done_icon

        return self.get_heading() + done_icon

    def fix_full_output(self, output: str):
        # remove any single byte \xXX escapes
        output = re.sub(r"(?<!\\)\\x[0-9A-Fa-f]{2}", "", output)
        # Strip every line of output before truncation
        # output = "\n".join(line.strip() for line in output.splitlines())
        output = truncate_text_agent(agent=self.agent, output=output, threshold=50000) # ~50KB belt-and-suspenders; compression gate further reduces to 2KB at perception layer
        return output

    async def ensure_cwd(self) -> str | None:
        project_name = projects.get_context_project_name(self.agent.context)
        if project_name:
            path = projects.get_project_folder(project_name)
        else:
            set = settings.get_settings()
            path = set.get("workdir_path")

        if not path:
            return None

        normalized = files.normalize_a0_path(path)
        await runtime.call_development_function(make_dir, normalized)
        return normalized

def make_dir(path: str):
    import os
    os.makedirs(path, exist_ok=True)
        

        