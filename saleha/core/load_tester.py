"""
Saleha Core: High-Concurrency API Load & Stress Tester

Executes multi-threaded HTTP traffic generation to benchmark throughput (RPS),
calculate percentile latencies (p50, p95, p99), and discover backend performance bottlenecks.
"""

import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class LoadTestResult:
    url: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    duration_sec: float
    requests_per_sec: float
    avg_latency_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float


class LoadTester:
    """Multi-threaded HTTP load generation and percentile benchmark engine."""

    def run_load_test(
        self,
        url: str = "http://localhost:8000/api",
        concurrency: int = 10,
        total_requests: int = 50,
        timeout_sec: float = 3.0,
        dry_run: bool = False
    ) -> LoadTestResult:
        """Executes concurrent load test against target URL."""
        if dry_run:
            return LoadTestResult(
                url=url,
                total_requests=total_requests,
                successful_requests=total_requests,
                failed_requests=0,
                duration_sec=0.12,
                requests_per_sec=round(total_requests / 0.12, 1),
                avg_latency_ms=2.4,
                p50_ms=2.1,
                p95_ms=4.8,
                p99_ms=6.2
            )

        latencies = []
        successes = 0
        failures = 0
        start_time = time.time()

        def _make_req():
            t0 = time.time()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Saleha-LoadTester/1.0"})
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    status = resp.getcode()
                    dur_ms = round((time.time() - t0) * 1000, 2)
                    return (200 <= status < 400), dur_ms
            except Exception:
                dur_ms = round((time.time() - t0) * 1000, 2)
                return False, dur_ms

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(_make_req) for _ in range(total_requests)]
            for fut in as_completed(futures):
                ok, lat = fut.result()
                latencies.append(lat)
                if ok:
                    successes += 1
                else:
                    failures += 1

        total_dur = round(time.time() - start_time, 2) or 0.01
        rps = round(total_requests / total_dur, 1)

        latencies.sort()
        avg_lat = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
        p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0

        return LoadTestResult(
            url=url,
            total_requests=total_requests,
            successful_requests=successes,
            failed_requests=failures,
            duration_sec=total_dur,
            requests_per_sec=rps,
            avg_latency_ms=avg_lat,
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99
        )


# Global instance
load_tester = LoadTester()

