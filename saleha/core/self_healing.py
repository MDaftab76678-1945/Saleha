"""
Saleha Core: Self-Healing & Error Reflexion Engine

Purpose: read a code execution or compilation error, identify its root cause,
and build a corrected (reflexion) instruction for the agent to retry with.

Note on language: this file's docstrings, comments and every string it
produces used to be Devanagari Hindi -- the same violation CLAUDE.md records
for `orchestrator.py` and `safety_guard.py`. That mattered here rather than
being cosmetic: `DebuggerAgent` embeds `root_cause_hint` verbatim into the
prompt it sends to the code model (`saleha/agents/debugger.py`), so a Hindi
sentence was being handed to a code model as its diagnosis of a Python
traceback, and `reflexion_prompt` was a fully Hindi instruction block.
"""

import re
from dataclasses import dataclass

# ==============================================================================
# 1. Error pattern matching
# These patterns scan an error log and classify the error by type. A pattern
# that matches nothing leaves the type as "UnknownError" -- see
# `error_detected` below, which reports that honestly rather than claiming a
# successful detection.
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
    # The prompt handed back to the agent so it can correct its own output.
    reflexion_prompt: str

# ==============================================================================
# 3. Core logic
# ==============================================================================

class SelfHealingEngine:
    def __init__(self):
        # Pre-compile the regex patterns for performance.
        self.compiled_errors = {
            err_type: re.compile(pattern, re.IGNORECASE) 
            for err_type, pattern in ERROR_PATTERNS.items()
        }

    def analyze_and_heal(self, error_log: str, original_task: str) -> HealingResult:
        """Analyzes an error log and builds a corrected prompt for the agent."""
        if not error_log or not error_log.strip():
            return HealingResult(
                error_detected=False, error_type="None",
                root_cause_hint="No error found.",
                reflexion_prompt=""
            )

        detected_type = "UnknownError"
        root_cause = ("The exact cause could not be classified. Check the "
                      "final lines of the log.")
        pattern_matched = False

        # 1. Identify the error type.
        for err_type, pattern in self.compiled_errors.items():
            if pattern.search(error_log):
                detected_type = err_type
                pattern_matched = True
                break

        # 2. Infer the likely root cause.
        if detected_type == "SyntaxError":
            root_cause = ("A grammar mistake in the code, such as an unclosed "
                          "bracket, a missing colon, or unbalanced quotes.")
        elif detected_type == "ImportError":
            root_cause = ("A required library is not installed, or the module "
                          "name/path is wrong.")
        elif detected_type == "IndentationError":
            root_cause = "The indentation (spaces/tabs) is inconsistent."
        elif detected_type == "TypeError":
            root_cause = ("Mismatched data types, such as adding a string to "
                          "an integer.")
        elif detected_type == "NameError":
            root_cause = ("A variable or function is used before it is "
                          "defined.")

        # 3. Build the reflexion prompt for self-correction.
        reflexion_prompt = f"""
        [SALEHA SELF-HEALING REFLEXION]
        Original Task: {original_task}
        Detected Error: {detected_type}
        Root Cause Hint: {root_cause}

        Instructions:
        1. Check the previous code for the '{detected_type}' described above.
        2. Do not repeat the same mistake.
        3. Fix the code and return only the final, corrected code.
        """

        return HealingResult(
            # error_detected used to be hardcoded True here regardless of
            # whether any pattern in ERROR_PATTERNS actually matched -- so
            # a log this engine could not classify ("UnknownError") still
            # reported error_detected=True, which is a claim of successful
            # detection, not the "I don't know" it actually is. Now true
            # only when a known error type was matched by name.
            error_detected=pattern_matched,
            error_type=detected_type,
            root_cause_hint=root_cause,
            reflexion_prompt=reflexion_prompt.strip()
        )

    def auto_patch_code(self, code: str) -> str:
        """
        Auto-patches small-model hallucinations and missing standard library imports
        before AST parsing and execution verification.
        """
        if not code or not code.strip():
            return code

        patched = code

        # 1. Fix missing stdlib imports
        needed_imports = []
        if re.search(r"\btime\.(?:sleep|time|monotonic|perf_counter)\b", patched) and not re.search(r"^\s*(?:import\s+time|from\s+time\s+import)", patched, re.M):
            needed_imports.append("import time")
        if re.search(r"\bjson\.(?:loads|dumps|load|dump)\b", patched) and not re.search(r"^\s*(?:import\s+json|from\s+json\s+import)", patched, re.M):
            needed_imports.append("import json")
        if re.search(r"\bos\.(?:path|environ|getcwd|listdir|makedirs)\b", patched) and not re.search(r"^\s*(?:import\s+os|from\s+os\s+import)", patched, re.M):
            needed_imports.append("import os")
        if re.search(r"\bsys\.(?:exit|argv|path|stdout)\b", patched) and not re.search(r"^\s*(?:import\s+sys|from\s+sys\s+import)", patched, re.M):
            needed_imports.append("import sys")
        if re.search(r"\bre\.(?:search|match|findall|sub|compile)\b", patched) and not re.search(r"^\s*(?:import\s+re|from\s+re\s+import)", patched, re.M):
            needed_imports.append("import re")
        if re.search(r"\bmath\.(?:sqrt|pi|pow|ceil|floor|log)\b", patched) and not re.search(r"^\s*(?:import\s+math|from\s+math\s+import)", patched, re.M):
            needed_imports.append("import math")

        if needed_imports:
            patched = "\n".join(needed_imports) + "\n\n" + patched

        # 2. Fix Java-style AtomicInteger hallucination
        patched = re.sub(r"\bAtomicInteger\((.*?)\)", r"\1", patched)
        patched = re.sub(r"(\w+)\.decrementAndGet\(\)", r"\1 = \1 - 1", patched)
        patched = re.sub(r"(\w+)\.incrementAndGet\(\)", r"\1 = \1 + 1", patched)
        patched = re.sub(r"(\w+)\.addAndGet\((.*?)\)", r"\1 = \1 + \2", patched)

        # 3. Fix Java/JS print statement hallucinations
        patched = re.sub(r"System\.out\.println\((.*?)\)", r"print(\1)", patched)  # noqa
        patched = re.sub(r"console\.log\((.*?)\)", r"print(\1)", patched)  # noqa

        return patched

# ==============================================================================
# 4. Testing
# ==============================================================================

if __name__ == "__main__":
    _engine = SelfHealingEngine()
    _res = _engine.analyze_and_heal("SyntaxError: invalid syntax", "def add(a, b): return a + b")