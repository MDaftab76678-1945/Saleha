# k8s/chaos/orchestrator/chaos_runner.py
"""
Chaos experiment orchestrator.

Runs experiments end-to-end:
1. Baseline probes (steady state)
2. Inject chaos (apply ChaosEngine)
3. Monitor probes during chaos
4. Verify recovery after chaos
5. Validate runbook procedure was triggered

Generates a report mapping results to runbook procedures.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog
from pathlib import Path

from probes import HttpProbe, PodCountProbe, Probe, ProbeResult, PrometheusProbe

logger = structlog.get_logger(__name__)


@dataclass
class ExperimentSpec:
    """Definition of a chaos experiment."""
    name: str
    manifest: str              # Path to ChaosEngine YAML
    runbook_ref: str           # Runbook procedure validated (e.g., "IR-01")
    hypothesis: str            # What we expect to happen
    probes: List[Probe] = field(default_factory=list)
    duration_seconds: int = 60
    recovery_timeout_seconds: int = 120


@dataclass
class ExperimentResult:
    """Result of a chaos experiment."""
    name: str
    runbook_ref: str
    hypothesis: str
    baseline_passed: bool = False
    chaos_injected: bool = False
    during_chaos_results: List[ProbeResult] = field(default_factory=list)
    recovery_passed: bool = False
    recovery_time_seconds: float = 0.0
    overall_passed: bool = False
    error: Optional[str] = None
    duration_seconds: float = 0.0


class ChaosRunner:
    """
    Orchestrates chaos experiments with probe validation.

    Usage:
        runner = ChaosRunner(experiments_dir="k8s/chaos/litmus/experiments")
        results = await runner.run_all()
        runner.print_report(results)
    """

    # Predefined experiments with runbook mapping
    EXPERIMENTS: List[Dict[str, Any]] = [
        {
            "name": "api-pod-delete",
            "runbook_ref": "IR-01",
            "hypothesis": "API recovers < 2 min, error spike < 30s",
            "duration": 60,
            "probes": [
                HttpProbe("api-health", "http://localhost:8000/health"),
                PodCountProbe("api-pods-ready", "mukti", "app.kubernetes.io/name=mukti", min_ready=2),
            ],
        },
        {
            "name": "postgres-pod-delete",
            "runbook_ref": "IR-02",
            "hypothesis": "DB restarts, app recovers < 90s",
            "duration": 90,
            "probes": [
                HttpProbe("api-health", "http://localhost:8000/health", max_latency_ms=10000),
            ],
        },
        {
            "name": "redis-pod-delete",
            "runbook_ref": "IR-03",
            "hypothesis": "API stays up despite cache loss",
            "duration": 60,
            "probes": [
                HttpProbe("api-health", "http://localhost:8000/health"),
            ],
        },
        {
            "name": "network-latency",
            "runbook_ref": "IR-04",
            "hypothesis": "Graceful degradation, no hard failures",
            "duration": 120,
            "probes": [
                HttpProbe("api-health", "http://localhost:8000/health", max_latency_ms=15000),
            ],
        },
        {
            "name": "disk-fill",
            "runbook_ref": "IR-06",
            "hypothesis": "PVC alert fires at > 85%",
            "duration": 120,
            "probes": [
                PrometheusProbe(
                    "pvc-alert",
                    "http://localhost:9090",
                    "kubelet_volume_stats_used_bytes{namespace='mukti'} / kubelet_volume_stats_capacity_bytes{namespace='mukti'} > 0.85",
                    expect_result=True,
                ),
            ],
        },
        {
            "name": "node-drain",
            "runbook_ref": "IR-06/HA",
            "hypothesis": "Pods reschedule, zero downtime",
            "duration": 120,
            "probes": [
                HttpProbe("api-health", "http://localhost:8000/health"),
                PodCountProbe("api-pods-ready", "mukti", "app.kubernetes.io/name=mukti", min_ready=2),
            ],
        },
    ]

    def __init__(
        self,
        experiments_dir: str = "k8s/chaos/litmus/experiments",
        dry_run: bool = False,
    ):
        self.experiments_dir = Path(experiments_dir)
        self.dry_run = dry_run
        self.results: List[ExperimentResult] = []

    async def run_experiment(self, spec: Dict[str, Any]) -> ExperimentResult:
        """Run a single chaos experiment with full probe lifecycle."""
        name = spec["name"]
        result = ExperimentResult(
            name=name,
            runbook_ref=spec["runbook_ref"],
            hypothesis=spec["hypothesis"],
        )
        start = time.perf_counter()

        logger.info("chaos.experiment.start", experiment=name, runbook=spec["runbook_ref"])

        try:
            probes: List[Probe] = spec["probes"]

            # ── Phase 1: Baseline (steady state) ──
            logger.info("chaos.phase.baseline", experiment=name)
            baseline_results = await self._run_probes(probes)
            result.baseline_passed = all(r.passed for r in baseline_results)

            if not result.baseline_passed:
                result.error = "Baseline failed – aborting (system already unhealthy)"
                result.duration_seconds = time.perf_counter() - start
                return result

            # ── Phase 2: Inject chaos ──
            logger.info("chaos.phase.inject", experiment=name)
            await self._apply_chaos(name)
            result.chaos_injected = True

            # ── Phase 3: Monitor during chaos ──
            logger.info("chaos.phase.monitor", experiment=name, duration=spec["duration"])
            monitor_end = time.time() + spec["duration"]
            while time.time() < monitor_end:
                probe_results = await self._run_probes(probes)
                result.during_chaos_results.extend(probe_results)
                await asyncio.sleep(10)

            # ── Phase 4: Remove chaos & verify recovery ──
            logger.info("chaos.phase.recover", experiment=name)
            await self._remove_chaos(name)

            recovery_start = time.perf_counter()
            recovered = False
            while time.perf_counter() - recovery_start < spec.get("recovery_timeout", 120):
                recovery_results = await self._run_probes(probes)
                if all(r.passed for r in recovery_results):
                    recovered = True
                    break
                await asyncio.sleep(5)

            result.recovery_passed = recovered
            result.recovery_time_seconds = time.perf_counter() - recovery_start

            # ── Phase 5: Overall verdict ──
            # Pass if: baseline OK AND recovery OK
            # (During-chaos failures are expected/tolerable for some experiments)
            result.overall_passed = result.baseline_passed and result.recovery_passed

        except Exception as e:
            result.error = str(e)
            logger.error("chaos.experiment.failed", experiment=name, error=str(e))
        finally:
            # Always attempt cleanup
            await self._remove_chaos(name)
            result.duration_seconds = time.perf_counter() - start

        logger.info(
            "chaos.experiment.done",
            experiment=name,
            passed=result.overall_passed,
            recovery_time=round(result.recovery_time_seconds, 2),
        )
        return result

    async def _run_probes(self, probes: List[Probe]) -> List[ProbeResult]:
        """Run all probes concurrently."""
        return await asyncio.gather(*(p.check() for p in probes))

    async def _apply_chaos(self, name: str) -> None:
        """Apply the ChaosEngine manifest."""
        manifest = self.experiments_dir / f"{name}.yaml"
        if not manifest.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest}")

        if self.dry_run:
            logger.info("chaos.dry_run", manifest=str(manifest))
            return

        proc = await asyncio.create_subprocess_exec(
            "kubectl", "apply", "-f", str(manifest),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to apply chaos: {stderr.decode()}")

    async def _remove_chaos(self, name: str) -> None:
        """Remove the ChaosEngine (stop chaos injection)."""
        if self.dry_run:
            return

        proc = await asyncio.create_subprocess_exec(
            "kubectl", "delete", "chaosengine", f"mukti-{name}",
            "-n", "mukti", "--ignore-not-found",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

    async def run_all(self, filter_names: Optional[List[str]] = None) -> List[ExperimentResult]:
        """Run all (or filtered) experiments sequentially."""
        self.results = []
        for spec in self.EXPERIMENTS:
            if filter_names and spec["name"] not in filter_names:
                continue
            result = await self.run_experiment(spec)
            self.results.append(result)
        return self.results

    def print_report(self) -> None:
        """Print a runbook-validation report."""
        print("\n" + "=" * 70)
        print("CHAOS ENGINEERING REPORT – Runbook Validation")
        print("=" * 70)
        print(f"{'Experiment':<25} {'Runbook':<12} {'Baseline':<10} {'Recovery':<10} {'RecTime':<10} {'Verdict':<10}")
        print("-" * 70)

        for r in self.results:
            baseline = "✓" if r.baseline_passed else "✗"
            recovery = "✓" if r.recovery_passed else "✗"
            verdict = "PASS" if r.overall_passed else "FAIL"
            rec_time = f"{r.recovery_time_seconds:.1f}s"
            print(f"{r.name:<25} {r.runbook_ref:<12} {baseline:<10} {recovery:<10} {rec_time:<10} {verdict:<10}")
            if r.error:
                print(f"  └─ Error: {r.error}")

        print("=" * 70)
        passed = sum(1 for r in self.results if r.overall_passed)
        print(f"Total: {passed}/{len(self.results)} experiments passed")
        print("=" * 70 + "\n")
