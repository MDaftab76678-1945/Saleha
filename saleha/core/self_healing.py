"""
Saleha Core: Self-Healing & Error Reflexion Engine.

Analyzes code execution or compilation errors, extracts structured Python traceback frames,
identifies the root cause, and generates an actionable reflexion prompt for iterative self-repair.
Also provides static AST/text auto-patching for missing standard library and typing imports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ==============================================================================
# 1. Error pattern matching
# ==============================================================================

ERROR_PATTERNS = {
    "SyntaxError": r"(SyntaxError|invalid syntax|EOL while scanning|unexpected EOF)",
    "ImportError": r"(ModuleNotFoundError|ImportError|No module named)",
    "TypeError": r"(TypeError|unsupported operand type|takes \d+ positional arguments)",
    "NameError": r"(NameError|name '\w+' is not defined)",
    "IndentationError": r"(IndentationError|expected an indented block)",
    "AttributeError": r"(AttributeError|'\w+' object has no attribute)",
    "PermissionError": r"(PermissionError|Access is denied)",
    "ZeroDivisionError": r"(ZeroDivisionError|division by zero|float division by zero)",
    "KeyError": r"(KeyError)",
    "IndexError": r"(IndexError|list index out of range|string index out of range)",
    "ValueError": r"(ValueError|invalid literal for|could not convert)",
    "RuntimeError": r"(RuntimeError|maximum recursion depth exceeded)",
}

# ==============================================================================
# 2. Data structures
# ==============================================================================


@dataclass
class HealingResult:
    error_detected: bool
    error_type: str
    root_cause_hint: str
    reflexion_prompt: str
    faulting_file: str = ""
    faulting_line: int = 0
    faulting_symbol: str = ""
    traceback_frames: List[Dict[str, Any]] = field(default_factory=list)


# ==============================================================================
# 3. Core logic
# ==============================================================================


class SelfHealingEngine:
    def __init__(self) -> None:
        self.compiled_errors = {
            err_type: re.compile(pattern, re.IGNORECASE)
            for err_type, pattern in ERROR_PATTERNS.items()
        }

    def extract_traceback_frames(self, error_log: str) -> List[Dict[str, Any]]:
        """
        Parses structured traceback frames from Python error logs.
        Pattern: File "path", line X, in func_name
        """
        if not error_log:
            return []
        pattern = re.compile(r'File "([^"]+)", line (\d+)(?:, in (\S+))?(?:\n\s*(.*))?')
        frames: List[Dict[str, Any]] = []
        for match in pattern.finditer(error_log):
            fpath, lno, symbol, code_line = match.groups()
            frames.append({
                "file": fpath.strip(),
                "line": int(lno),
                "symbol": symbol.strip() if symbol else "",
                "code_line": code_line.strip() if code_line else "",
            })
        return frames

    def analyze_and_heal(self, error_log: str, original_task: str) -> HealingResult:
        """Analyzes an error log, extracts tracebacks, and builds a corrected prompt for the agent."""
        if not error_log or not error_log.strip():
            return HealingResult(
                error_detected=False,
                error_type="None",
                root_cause_hint="No error found.",
                reflexion_prompt="",
            )

        detected_type = "UnknownError"
        root_cause = (
            "The exact cause could not be classified. Check the final lines of the log."
        )
        pattern_matched = False

        # 1. Identify the error type
        for err_type, pattern in self.compiled_errors.items():
            if pattern.search(error_log):
                detected_type = err_type
                pattern_matched = True
                break

        # 2. Infer the likely root cause
        if detected_type == "SyntaxError":
            root_cause = (
                "A grammar mistake in the code, such as an unclosed bracket, a missing colon, "
                "or unbalanced quotes."
            )
        elif detected_type == "ImportError":
            root_cause = (
                "A required library is not installed, or the module name/path is wrong."
            )
        elif detected_type == "IndentationError":
            root_cause = "The indentation (spaces/tabs) is inconsistent."
        elif detected_type == "TypeError":
            root_cause = (
                "Mismatched data types, such as adding a string to an integer."
            )
        elif detected_type == "NameError":
            root_cause = "A variable or function is used before it is defined."
        elif detected_type == "ZeroDivisionError":
            root_cause = "Division by zero encountered in arithmetic expression."
        elif detected_type == "AttributeError":
            root_cause = "Attempted to access an attribute or method that does not exist on the object."
        elif detected_type == "IndexError":
            root_cause = "List or sequence index is out of bounds."
        elif detected_type == "KeyError":
            root_cause = "Dictionary key does not exist in the collection."

        # 3. Extract traceback frames and localize defect
        frames = self.extract_traceback_frames(error_log)
        faulting_file = ""
        faulting_line = 0
        faulting_symbol = ""
        location_line = ""

        if frames:
            last_frame = frames[-1]
            faulting_file = last_frame["file"]
            faulting_line = last_frame["line"]
            faulting_symbol = last_frame["symbol"]
            sym_desc = f" (in {faulting_symbol})" if faulting_symbol else ""
            location_line = f"\n        Faulting Location: {faulting_file}:{faulting_line}{sym_desc}"
            if last_frame.get("code_line"):
                location_line += f"\n        Failing Code: {last_frame['code_line']}"

        # 4. Build the reflexion prompt for self-correction
        reflexion_prompt = f"""
        [SALEHA SELF-HEALING REFLEXION]
        Original Task: {original_task}
        Detected Error: {detected_type}{location_line}
        Root Cause Hint: {root_cause}

        Instructions:
        1. Check the previous code for the '{detected_type}' described above.
        2. Do not repeat the same mistake.
        3. Fix the code and return only the final, corrected code.
        """

        return HealingResult(
            error_detected=pattern_matched,
            error_type=detected_type,
            root_cause_hint=root_cause,
            reflexion_prompt=reflexion_prompt.strip(),
            faulting_file=faulting_file,
            faulting_line=faulting_line,
            faulting_symbol=faulting_symbol,
            traceback_frames=frames,
        )

    def auto_patch_code(self, code: str) -> str:
        """
        Auto-patches small-model hallucinations and missing standard library/typing imports
        before AST parsing and execution verification.
        """
        if not code or not code.strip():
            return code

        patched = code
        needed_imports: List[str] = []

        # 1. Fix missing stdlib imports
        if re.search(r"\btime\.(?:sleep|time|monotonic|perf_counter)\b", patched) and not re.search(
            r"^\s*(?:import\s+time|from\s+time\s+import)", patched, re.M
        ):
            needed_imports.append("import time")
        if re.search(r"\bjson\.(?:loads|dumps|load|dump)\b", patched) and not re.search(
            r"^\s*(?:import\s+json|from\s+json\s+import)", patched, re.M
        ):
            needed_imports.append("import json")
        if re.search(r"\bos\.(?:path|environ|getcwd|listdir|makedirs)\b", patched) and not re.search(
            r"^\s*(?:import\s+os|from\s+os\s+import)", patched, re.M
        ):
            needed_imports.append("import os")
        if re.search(r"\bsys\.(?:exit|argv|path|stdout)\b", patched) and not re.search(
            r"^\s*(?:import\s+sys|from\s+sys\s+import)", patched, re.M
        ):
            needed_imports.append("import sys")
        if re.search(r"\bre\.(?:search|match|findall|sub|compile)\b", patched) and not re.search(
            r"^\s*(?:import\s+re|from\s+re\s+import)", patched, re.M
        ):
            needed_imports.append("import re")
        if re.search(r"\bmath\.(?:sqrt|pi|pow|ceil|floor|log)\b", patched) and not re.search(
            r"^\s*(?:import\s+math|from\s+math\s+import)", patched, re.M
        ):
            needed_imports.append("import math")

        # 2. Fix missing typing imports
        typing_symbols = ["Any", "Dict", "List", "Optional", "Tuple", "Set", "Union", "Callable"]
        needed_typing = [
            sym
            for sym in typing_symbols
            if re.search(r"\b" + sym + r"\[", patched)
            and not re.search(r"^\s*(?:from\s+typing\s+import|import\s+typing)", patched, re.M)
        ]
        if needed_typing and not re.search(
            r"^\s*(?:from\s+typing\s+import|import\s+typing)", patched, re.M
        ):
            needed_imports.append(f"from typing import {', '.join(sorted(needed_typing))}")

        # 3. Fix missing pathlib import
        if re.search(r"\bPath\(", patched) and not re.search(
            r"^\s*(?:from\s+pathlib\s+import\s+Path|import\s+pathlib)", patched, re.M
        ):
            needed_imports.append("from pathlib import Path")

        if needed_imports:
            patched = "\n".join(needed_imports) + "\n\n" + patched

        # 4. Fix Java-style AtomicInteger hallucination
        patched = re.sub(r"\bAtomicInteger\((.*?)\)", r"\1", patched)
        patched = re.sub(r"(\w+)\.decrementAndGet\(\)", r"\1 = \1 - 1", patched)
        patched = re.sub(r"(\w+)\.incrementAndGet\(\)", r"\1 = \1 + 1", patched)
        patched = re.sub(r"(\w+)\.addAndGet\((.*?)\)", r"\1 = \1 + \2", patched)

        # 5. Fix Java/JS print statement hallucinations
        patched = re.sub(r"System\.out\.println\((.*?)\)", r"print(\1)", patched)
        patched = re.sub(r"console\.log\((.*?)\)", r"print(\1)", patched)

        return patched