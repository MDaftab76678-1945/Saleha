"""
Saleha Core: Autonomous Bug Bounty & API Fuzzing Agent

Executes security mutation fuzzing (SQL injection, XSS, integer overflows, null-byte injections,
format strings, and malformed JSON payloads) against API endpoints and code functions to discover
unhandled 500 crashes and zero-day vulnerabilities.
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from saleha.core.code_executor import CodeExecutor


@dataclass
class FuzzingFinding:
    category: str  # 'SQLi', 'XSS', 'Overflow', 'NullByte', 'MalformedJSON'
    payload: str
    status: str
    vulnerability_detected: bool
    details: str = ""


@dataclass
class FuzzingReport:
    target: str
    total_mutations: int
    vulnerabilities_found: int
    crashes_found: int
    findings: List[FuzzingFinding] = field(default_factory=list)


MUTATION_PAYLOADS: List[Dict[str, str]] = [
    {"category": "SQLi", "payload": "' OR '1'='1", "desc": "Classic SQL boolean bypass"},
    {"category": "SQLi", "payload": "'; DROP TABLE users; --", "desc": "Stacked query injection"},
    {"category": "XSS", "payload": "<script>alert('XSS')</script>", "desc": "Basic script injection"},
    {"category": "XSS", "payload": "\"><img src=x onerror=alert(1)>", "desc": "Event handler injection"},
    {"category": "Overflow", "payload": "999999999999999999999999999999999999999999", "desc": "Bigint overflow"},
    {"category": "Overflow", "payload": "A" * 5000, "desc": "Buffer string overflow"},
    {"category": "NullByte", "payload": "admin%00.jpg", "desc": "Null-byte file bypass"},
    {"category": "MalformedJSON", "payload": '{"key": "val",}', "desc": "Trailing comma invalid JSON"},
    {"category": "TypeConfusion", "payload": "[null, false, -1]", "desc": "Type confusion array payload"}
]


class APIFuzzer:
    """Automated security fuzzing and mutation testing engine."""

    def __init__(self):
        self.executor = CodeExecutor()

    def fuzz_function(self, code: str, func_name: str = "process", mutations: int = 10) -> FuzzingReport:
        """Fuzzes a Python function with diverse mutation payloads."""
        findings = []
        payloads_to_run = MUTATION_PAYLOADS[:mutations]
        vulns_count = 0
        crashes_count = 0

        for p in payloads_to_run:
            test_script = (
                f"{code}\n\n"
                f"try:\n"
                f"    res = {func_name}({repr(p['payload'])})\n"
                f"    print('FUZZ_SAFE')\n"
                f"except Exception as e:\n"
                f"    print(f'FUZZ_CRASH: {{e}}')\n"
            )
            exec_res = self.executor.execute(test_script)
            output = exec_res.output

            if "FUZZ_CRASH" in output:
                crashes_count += 1
                findings.append(FuzzingFinding(
                    category=p["category"],
                    payload=p["payload"][:50],
                    status="CRASH",
                    vulnerability_detected=True,
                    details=output.strip()
                ))
                vulns_count += 1
            else:
                findings.append(FuzzingFinding(
                    category=p["category"],
                    payload=p["payload"][:50],
                    status="SAFE",
                    vulnerability_detected=False,
                    details="Handled gracefully without unhandled exception."
                ))

        return FuzzingReport(
            target=func_name,
            total_mutations=len(payloads_to_run),
            vulnerabilities_found=vulns_count,
            crashes_found=crashes_count,
            findings=findings
        )


# Global instance
api_fuzzer = APIFuzzer()

