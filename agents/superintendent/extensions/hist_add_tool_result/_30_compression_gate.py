"""
Compression Gate — Epistemic Truncation for Tool Results

Fires at hist_add_tool_result (_30, BEFORE SaveToolCallFile _90).
Strips __METABOLIC_DATA__ metadata prefix from code_execution_tool,
truncates large outputs to MAX_OUTPUT_CHARS with 60/40 head/tail split,
writes full dumps to /tmp/mogul_tool_dumps/ for forensic access,
and prepends a human-readable metabolic receipt.

Design principle: The agent should see cost awareness but not raw data
floods. 2000 chars is enough context for any tool result — if the agent
needs more, it should use targeted commands (grep, jq, head, wc -l).

Fail-silent: truncation and dump errors never crash the tool pipeline.
"""

import os
from datetime import datetime
from typing import Any
from python.helpers.extension import Extension

MAX_OUTPUT_CHARS = 2000
DUMP_DIR = "/tmp/mogul_tool_dumps"
MAX_DUMP_FILES = 50


class CompressionGate(Extension):
    async def execute(self, data: dict[str, Any] | None = None, **kwargs):
        if not data or not isinstance(data, dict):
            return

        tool_result = data.get("tool_result")
        if not tool_result or not isinstance(tool_result, str):
            return

        # 1. EXTRACT METADATA
        raw_chars = 0
        cost = 0
        balance = 0
        has_metadata = False

        if tool_result.startswith("__METABOLIC_DATA__:"):
            first_nl = tool_result.find("\n")
            if first_nl == -1:
                meta_line = tool_result
                tool_result = ""
            else:
                meta_line = tool_result[:first_nl]
                tool_result = tool_result[first_nl + 1:]

            try:
                parts = meta_line.split(":", 1)[1].split("|")
                raw_chars = int(parts[0])
                cost = int(parts[1])
                balance = int(parts[2])
                has_metadata = True
            except (IndexError, ValueError):
                pass

        # 2. TRUNCATION (if output exceeds budget)
        truncated = False
        dump_path = ""

        if len(tool_result) > MAX_OUTPUT_CHARS:
            truncated = True

            # Write full output to dump dir
            try:
                os.makedirs(DUMP_DIR, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                tool_name = data.get("tool_name", "unknown")
                safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in tool_name)
                dump_filename = f"{timestamp}_{safe_name}.txt"
                dump_path = os.path.join(DUMP_DIR, dump_filename)
                with open(dump_path, "w") as f:
                    f.write(tool_result)
            except Exception:
                dump_path = "(dump failed)"

            # Dump hygiene: cap file count
            try:
                dump_files = sorted(os.listdir(DUMP_DIR))
                while len(dump_files) > MAX_DUMP_FILES:
                    oldest = dump_files.pop(0)
                    os.remove(os.path.join(DUMP_DIR, oldest))
            except Exception:
                pass

            # Dynamic budget for head/tail
            receipt_overhead = 350 if has_metadata else 200
            available = max(MAX_OUTPUT_CHARS - receipt_overhead, 200)
            head_chars = int(available * 0.6)
            tail_chars = int(available * 0.4)
            omitted = len(tool_result) - head_chars - tail_chars

            tool_result = (
                tool_result[:head_chars]
                + f"\n...[TRUNCATED {omitted} chars, full: {dump_path}]...\n"
                + tool_result[-tail_chars:]
            )

        # 3. FORMAT METABOLIC RECEIPT
        receipt = ""
        if has_metadata:
            receipt = (
                f"[METABOLIC RECEIPT] Tool cost: {cost} nUC for "
                f"{raw_chars} raw chars. Balance: {balance} nUC."
            )
            if truncated:
                receipt += (
                    "\n[WARNING]: Highly inefficient operation. Brute-force "
                    "data dumps drain your cognitive budget. Use targeted "
                    "commands (grep, jq, head, wc -l) to preserve U-Coin."
                )

        # 4. ASSEMBLE FINAL OUTPUT
        if receipt:
            data["tool_result"] = receipt + "\n\n" + tool_result
        else:
            data["tool_result"] = tool_result
