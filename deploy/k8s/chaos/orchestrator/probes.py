# k8s/chaos/orchestrator/probes.py
"""
Steady-state probes for chaos experiments.

Probes run before/during/after chaos to validate hypotheses
and the corresponding runbook recovery procedures.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ProbeResult:
    """Result of a single probe check."""
    name: str
    passed: bool
    value: Any = None
    expected: Any = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class Probe:
    """Base probe that checks a condition."""

    def __init__(self, name: str, timeout: float = 10.0):
        self.name = name
        self.timeout = timeout

    async def check(self) -> ProbeResult:
        raise NotImplementedError


class HttpProbe(Probe):
    """Checks an HTTP endpoint for expected status."""

    def __init__(
        self,
        name: str,
        url: str,
        expected_status: int = 200,
        max_latency_ms: float = 5000.0,
        timeout: float = 10.0,
    ):
        super().__init__(name, timeout)
        self.url = url
        self.expected_status = expected_status
        self.max_latency_ms = max_latency_ms

    async def check(self) -> ProbeResult:
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(self.url)
            duration_ms = (time.perf_counter() - start) * 1000

            passed = (
                resp.status_code == self.expected_status
                and duration_ms <= self.max_latency_ms
            )
            return ProbeResult(
                name=self.name,
                passed=passed,
                value={"status": resp.status_code, "latency_ms": round(duration_ms, 2)},
                expected={"status": self.expected_status, "max_latency_ms": self.max_latency_ms},
                duration_ms=duration_ms,
            )
        except Exception as e:
            return ProbeResult(
                name=self.name,
                passed=False,
                error=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )


class PrometheusProbe(Probe):
    """Checks a PromQL query returns a truthy result."""

    def __init__(
        self,
        name: str,
        prometheus_url: str,
        query: str,
        expect_result: bool = True,
        timeout: float = 10.0,
    ):
        super().__init__(name, timeout)
        self.prometheus_url = prometheus_url
        self.query = query
        self.expect_result = expect_result

    async def check(self) -> ProbeResult:
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": self.query},
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("data", {}).get("result", [])
            has_result = len(results) > 0
            passed = has_result == self.expect_result

            return ProbeResult(
                name=self.name,
                passed=passed,
                value={"result_count": len(results)},
                expected={"expect_result": self.expect_result},
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return ProbeResult(
                name=self.name, passed=False, error=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )


class PodCountProbe(Probe):
    """Checks pod count meets minimum (HA validation)."""

    def __init__(
        self,
        name: str,
        namespace: str,
        label_selector: str,
        min_ready: int,
        timeout: float = 10.0,
    ):
        super().__init__(name, timeout)
        self.namespace = namespace
        self.label_selector = label_selector
        self.min_ready = min_ready

    async def check(self) -> ProbeResult:
        """Uses kubectl to count ready pods."""
        import asyncio
        start = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                "kubectl", "get", "pods",
                "-n", self.namespace,
                "-l", self.label_selector,
                "--field-selector=status.phase=Running",
                "-o", "name",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            count = len(stdout.decode().strip().splitlines())
            passed = count >= self.min_ready

            return ProbeResult(
                name=self.name,
                passed=passed,
                value={"ready_pods": count},
                expected={"min_ready": self.min_ready},
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return ProbeResult(
                name=self.name, passed=False, error=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )
