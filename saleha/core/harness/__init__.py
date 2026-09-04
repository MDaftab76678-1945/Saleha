"""
Saleha Core: Harness Engineering Subsystem (2026 Frontier Standard)

Provides isolated execution sandboxes, machine-checkable goal conditions,
multi-language test parsing, and deterministic benchmark evaluation:
- TestRunner / test_runner (Subprocess test runner with multi-language parsing: Pytest, Vitest, Cargo)
- CodeExecutor / code_executor (Contained subprocess execution with CPU/memory quotas)
- SandboxRunner / sandbox_runner (Isolated execution environments)
- ApprovalGate / approval_gate (Human-in-the-loop security permissions)
- SWEBenchRunner / swebench_runner (Autonomous SWE-Bench evaluation harness)
- BenchmarkHarness / benchmark_harness (Standardized multi-model capability scorecards)
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from saleha.core.test_runner import TestRunner, test_runner, TestSuiteResult, SuiteFailure

from saleha.core.code_executor import CodeExecutor, code_executor
from saleha.core.sandbox_runner import SandboxRunner, sandbox_runner
from saleha.core.approval_gate import ApprovalGate, approval_gate
from saleha.core.swebench_runner import (
    SWEBenchRunner,
    swebench_runner,
    SWEBenchTask,
    SWEBenchTaskOutcome,
    SWEBenchBenchmarkReport,
)
from saleha.core.benchmark_harness import BenchmarkHarness, benchmark_harness


@dataclass
class StructuredTestOutcome:
    """Standardized machine-checkable test result across polyglot test runners."""
    framework: str          # "pytest", "vitest", "cargo", "generic"
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_sec: float = 0.0
    failure_details: List[str] = field(default_factory=list)
    success: bool = False


class PolyglotHarnessParser:
    """
    Parses test execution outputs into machine-checkable goal verification structures:
    - Pytest (Python)
    - Vitest / Jest (TypeScript / JavaScript)
    - Cargo Test (Rust)
    """

    @staticmethod
    def parse_pytest(output: str) -> StructuredTestOutcome:
        """Parses pytest summary line (e.g. '10 passed, 2 failed, 1 skipped in 1.45s')."""
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        duration = 0.0
        failures = []

        m_pass = re.search(r"(\d+)\s+passed", output)
        if m_pass:
            passed = int(m_pass.group(1))

        m_fail = re.search(r"(\d+)\s+failed", output)
        if m_fail:
            failed = int(m_fail.group(1))

        m_skip = re.search(r"(\d+)\s+skipped", output)
        if m_skip:
            skipped = int(m_skip.group(1))

        m_err = re.search(r"(\d+)\s+error", output)
        if m_err:
            errors = int(m_err.group(1))

        m_dur = re.search(r"in\s+([0-9.]+)\s*s", output)
        if m_dur:
            duration = float(m_dur.group(1))

        for line in output.splitlines():
            if line.startswith("FAILED ") or line.startswith("ERROR "):
                failures.append(line.strip())

        is_success = (failed == 0 and errors == 0 and (passed > 0 or skipped > 0))
        return StructuredTestOutcome(
            framework="pytest",
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            duration_sec=duration,
            failure_details=failures[:20],
            success=is_success,
        )

    @staticmethod
    def parse_cargo_test(output: str) -> StructuredTestOutcome:
        """Parses Rust cargo test summary (e.g. 'test result: ok. 14 passed; 0 failed')."""
        m = re.search(r"test result:\s+(\w+)\.\s+(\d+)\s+passed;\s+(\d+)\s+failed;\s+(\d+)\s+ignored", output)
        if m:
            status, passed, failed, ignored = m.groups()
            return StructuredTestOutcome(
                framework="cargo",
                passed=int(passed),
                failed=int(failed),
                skipped=int(ignored),
                success=(status == "ok" and int(failed) == 0),
            )
        return StructuredTestOutcome(
            framework="cargo",
            success="test result: ok" in output,
        )


__all__ = [
    "TestRunner",
    "test_runner",
    "TestSuiteResult",
    "SuiteFailure",
    "CodeExecutor",
    "code_executor",

    "SandboxRunner",
    "sandbox_runner",
    "ApprovalGate",
    "approval_gate",
    "SWEBenchRunner",
    "swebench_runner",
    "SWEBenchTask",
    "SWEBenchTaskOutcome",
    "SWEBenchBenchmarkReport",
    "BenchmarkHarness",
    "benchmark_harness",
    "StructuredTestOutcome",
    "PolyglotHarnessParser",
]
