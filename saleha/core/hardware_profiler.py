"""
Saleha Core: Hardware Profiler (v1.6 -- deep, psutil-powered)

Purana telemetry.py shallow tha aur dead-code ban gaya tha. Ye version:

  - CPU: overall %, per-core %, frequency, load-average (unix)
  - Memory: used/available/percent + swap
  - Disk I/O: read/write bytes counters + throughput delta
  - Network I/O: sent/recv counters + rates
  - Top processes by CPU/MEM (Saleha ke apne process highlighted)
  - Rolling history ring-buffer + windowed report aggregation

GPU note (honest): psutil GPU nahi deta. Agar nvidia-smi PATH par hai to
optional probe usko bhi include karta hai; warna gpu=None.

CLI: `saleha profile [--watch N] [--json]`
"""

import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    import psutil
    PSUTIL_OK = True
except ImportError:  # pragma: no cover
    PSUTIL_OK = False


@dataclass
class HardwareSnapshot:
    ts: float
    cpu_percent: float = 0.0
    cpu_per_core: List[float] = field(default_factory=list)
    cpu_freq_mhz: Optional[float] = None
    load_avg: Optional[List[float]] = None
    mem_used_mb: float = 0.0
    mem_total_mb: float = 0.0
    mem_percent: float = 0.0
    swap_percent: float = 0.0
    disk_read_mb_s: float = 0.0
    disk_write_mb_s: float = 0.0
    net_sent_kb_s: float = 0.0
    net_recv_kb_s: float = 0.0
    top_processes: List[Dict] = field(default_factory=list)
    self_pid: int = 0
    gpu: Optional[Dict] = None


def _maybe_gpu() -> Optional[Dict]:
    """nvidia-smi optional probe -- na mile to None (koi hard dep nahi)."""
    import shutil
    import subprocess
    if not shutil.which("nvidia-smi"):
        return None
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        name, util, mem = [x.strip() for x in r.stdout.splitlines()[0].split(",")]
        return {"name": name, "util_percent": float(util), "mem_used_mb": float(mem)}
    except Exception:
        return None


class HardwareProfiler:
    def __init__(self, history_size: int = 600):
        if not PSUTIL_OK:
            raise RuntimeError("psutil required for HardwareProfiler")
        self.history = deque(maxlen=history_size)
        self._last_disk = psutil.disk_io_counters()
        self._last_net = psutil.net_io_counters()
        self._last_ts = time.time()
        self.self_pid = os.getpid()

    # ------------------------------------------------------------------
    def snapshot(self) -> HardwareSnapshot:
        snap = HardwareSnapshot(ts=time.time(), self_pid=self.self_pid)
        snap.cpu_percent = psutil.cpu_percent(interval=0.15)
        snap.cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
        try:
            freq_fn = getattr(psutil, "cpu_freq", None)
            freq = freq_fn() if freq_fn else None
            snap.cpu_freq_mhz = round(freq.current, 0) if (freq and getattr(freq, "current", None) is not None) else None
        except (AttributeError, OSError, Exception):
            snap.cpu_freq_mhz = None

        try:
            la = psutil.getloadavg()
            snap.load_avg = [round(x, 2) for x in la]
        except (AttributeError, OSError, Exception):
            snap.load_avg = None

        vm = psutil.virtual_memory()
        snap.mem_used_mb = round(vm.used / 1_048_576, 1)
        snap.mem_total_mb = round(vm.total / 1_048_576, 1)
        snap.mem_percent = vm.percent

        try:
            sm = psutil.swap_memory()
            snap.swap_percent = sm.percent
        except (AttributeError, OSError, Exception):
            snap.swap_percent = 0.0

        now = time.time()
        dt = max(0.001, now - self._last_ts)
        disk_now = psutil.disk_io_counters()
        if disk_now and self._last_disk:
            snap.disk_read_mb_s = round(
                (disk_now.read_bytes - self._last_disk.read_bytes) / dt / 1_048_576, 2)
            snap.disk_write_mb_s = round(
                (disk_now.write_bytes - self._last_disk.write_bytes) / dt / 1_048_576, 2)
        net_now = psutil.net_io_counters()
        if net_now and self._last_net:
            snap.net_sent_kb_s = round(
                (net_now.bytes_sent - self._last_net.bytes_sent) / dt / 1024, 1)
            snap.net_recv_kb_s = round(
                (net_now.bytes_recv - self._last_net.bytes_recv) / dt / 1024, 1)
        self._last_disk, self._last_net, self._last_ts = disk_now, net_now, now

        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: (x.get("cpu_percent") or 0), reverse=True)
        snap.top_processes = [
            {"pid": p["pid"], "name": str(p.get("name"))[:24],
             "cpu": p.get("cpu_percent"), "mem_pct": p.get("memory_percent")}
            for p in procs[:6]
        ]
        if not any(p["pid"] == self.self_pid for p in snap.top_processes):
            try:
                me = psutil.Process(self.self_pid)
                snap.top_processes.append({
                    "pid": self.self_pid, "name": "saleha (self)",
                    "cpu": me.cpu_percent(), "mem_pct": me.memory_percent(),
                })
            except psutil.Error:
                pass
        snap.gpu = _maybe_gpu()

        self.history.append(snap)
        return snap

    # ------------------------------------------------------------------
    def record_window(self, seconds: float = 3.0, interval: float = 0.75) -> HardwareSnapshot:
        """`seconds` tak sample karke averaged final snapshot (live watch)."""
        end = time.time() + seconds
        snap = self.snapshot()
        while time.time() < end:
            time.sleep(max(0.2, interval))
            snap = self.snapshot()
        return snap

    def report(self, snaps: Optional[List[HardwareSnapshot]] = None) -> Dict:
        snaps = list(snaps if snaps is not None else self.history)[-120:]
        if not snaps:
            return {"samples": 0}
        avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else 0.0  # noqa: E731
        peak_cpu = max(s.cpu_percent for s in snaps)
        peak_mem = max(s.mem_percent for s in snaps)
        return {
            "samples": len(snaps),
            "avg_cpu": avg([s.cpu_percent for s in snaps]),
            "peak_cpu": peak_cpu,
            "avg_mem_percent": avg([s.mem_percent for s in snaps]),
            "peak_mem_percent": peak_mem,
            "avg_disk_write_mb_s": avg([s.disk_write_mb_s for s in snaps]),
            "avg_net_recv_kb_s": avg([s.net_recv_kb_s for s in snaps]),
            "window_sec": round(snaps[-1].ts - snaps[0].ts, 1),
        }


def get_profiler() -> Optional[HardwareProfiler]:
    """Shared profiler instance (process-lifetime)."""
    global _shared_profiler
    if not PSUTIL_OK:
        return None
    if _shared_profiler is None:
        _shared_profiler = HardwareProfiler()
    return _shared_profiler


# Shared singleton (lazy)
_shared_profiler: Optional[HardwareProfiler] = None
