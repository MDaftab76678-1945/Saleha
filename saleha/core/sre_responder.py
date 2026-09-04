"""
Saleha Core: Incident Log Parser & Generic Hotfix Template Picker

Parses Python and JS stack traces with regexes to identify the exception
type, message, and offending file/line -- that part is genuine text
extraction, not fabricated.

`hotfix_patch`, however, is not a patch synthesized from the actual failing
code: it is one of four fixed generic snippets selected purely by exception
type (ZeroDivisionError / KeyError+IndexError / AttributeError / anything
else), using placeholder names like `denominator` and `target_dict` that are
not the real variable names from the analyzed code. It is a copy-paste
starting point for a human to adapt, not code Saleha derived from the
incident -- despite an earlier version of this docstring calling it
"synthesized". See `saleha.core.self_healer` for the module that actually
generates a fix by running and inspecting the specific failing code.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class SREIncidentReport:
    error_type: str
    error_message: str
    offending_file: Optional[str]
    offending_line: Optional[int]
    root_cause_analysis: str
    hotfix_patch: str
    hotfix_is_generic_template: bool
    severity: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'


class SREResponder:
    """Automates production incident analysis and emergency hotfix patch synthesis."""

    def analyze_log(self, log_content: str) -> SREIncidentReport:
        """Parses error tracebacks and produces Root Cause Analysis."""
        error_type = "UnknownError"
        error_message = "No clear exception pattern detected."
        offending_file = None
        offending_line = None
        severity = "MEDIUM"

        # Python Traceback Pattern
        py_match = re.findall(r'File "([^"]+)", line (\d+), in (\w+)', log_content)
        if py_match:
            offending_file, line_str, func_name = py_match[-1]
            offending_line = int(line_str)

        # Exception type & message
        exc_match = re.findall(r'([a-zA-Z0-9_]+Error|[a-zA-Z0-9_]+Exception):\s*(.*)', log_content)
        if exc_match:
            error_type, error_message = exc_match[-1]
            severity = "CRITICAL" if any(k in error_type for k in ("Memory", "Syntax", "ZeroDivision", "Connection")) else "HIGH"

        # JS Stack Trace Pattern
        if not offending_file:
            js_match = re.findall(r'at\s+([a-zA-Z0-9_]+)\s+\(([^:]+):(\d+):(\d+)\)', log_content)
            if js_match:
                func_name, offending_file, line_str, _ = js_match[0]
                offending_line = int(line_str)
                severity = "HIGH"

        rca = (
            f"The application triggered an unhandled `{error_type}` with message: '{error_message}'. "
            f"Execution halted in `{offending_file or 'unknown'}` at line `{offending_line or 'N/A'}`."
        )

        # Generate Hotfix Patch
        if error_type == "ZeroDivisionError":
            hotfix = (
                f"# Emergency Hotfix for ZeroDivisionError at line {offending_line}\n"
                f"if denominator == 0:\n"
                f"    return 0.0  # Safe fallback default value\n"
            )
        elif error_type in ("KeyError", "IndexError"):
            hotfix = (
                f"# Emergency Hotfix for {error_type} at line {offending_line}\n"
                f"value = target_dict.get(key, default_fallback)\n"
            )
        elif error_type == "AttributeError":
            hotfix = (
                f"# Emergency Hotfix for NoneType check at line {offending_line}\n"
                f"if target_obj is not None:\n"
                f"    target_obj.call_method()\n"
            )
        else:
            hotfix = (
                f"# Defensive Exception Guard for {error_type}\n"
                f"try:\n"
                f"    # execute critical block\n"
                f"except {error_type} as err:\n"
                f"    logger.warning(f'Recovered gracefully from incident: {{err}}')\n"
            )

        return SREIncidentReport(
            error_type=error_type,
            error_message=error_message,
            offending_file=offending_file,
            offending_line=offending_line,
            root_cause_analysis=rca,
            hotfix_patch=hotfix,
            hotfix_is_generic_template=True,
            severity=severity
        )


# Global instance
sre_responder = SREResponder()

