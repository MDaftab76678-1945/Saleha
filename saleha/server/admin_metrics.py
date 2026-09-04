"""
Saleha Admin Panel data aggregation.

Every figure this module returns is read from data the system actually recorded
during real use. Sources that look like telemetry but are not are deliberately
excluded, and the reasons are documented here so nobody re-adds them by mistake:

- ``saleha.core.token_analytics`` is NOT surfaced. Its code is real, but nothing
  in the product ever calls ``record_invocation()`` -- the only writer in the
  repository is a test. The values on disk are identical synthetic fixtures, and
  ``gpt4o_equivalent_saved`` is a fixed multiple of the Claude figure rather than
  anything computed from GPT-4o rates. Showing token counts or "dollars saved"
  from it would be inventing numbers.
- ``saleha.core.session_tracer`` records genuine timings, but the singleton is
  per-process and the web server never opens spans, so it would always report an
  empty trace here.
- ``NanosecondLatencyHistogram`` has no shared instance and persists nothing;
  every caller builds a throwaway one.
- ``/api/workflow/dag``, ``/api/hardware/accel`` and ``/api/vault/ticker`` return
  hardcoded literals (the hardware probe reports ``npu_detected`` unconditionally
  and fixed tokens-per-second constants), so they are not aggregated here.

Each payload carries a ``sources`` block naming the file behind the numbers, so
the panel can show the reader where a figure came from.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

# The audit log is append-only and already ~2 MB; both reads below parse the
# whole file, so results are cached briefly rather than re-scanned per request.
_AUDIT_CACHE_TTL_SECONDS = 30.0


class _TtlCache:
    def __init__(self, ttl_seconds: float):
        self._ttl = ttl_seconds
        self._entries: Dict[str, Any] = {}

    def get_or_compute(self, key: str, compute):
        now = time.monotonic()
        cached = self._entries.get(key)
        if cached is not None and (now - cached[0]) < self._ttl:
            return cached[1]
        value = compute()
        self._entries[key] = (now, value)
        return value

    def invalidate(self) -> None:
        self._entries.clear()


_audit_cache = _TtlCache(_AUDIT_CACHE_TTL_SECONDS)


def _saleha_home() -> str:
    return os.path.join(os.path.expanduser("~"), ".saleha")


def _file_info(filename: str) -> Dict[str, Any]:
    """Reports whether a data file exists and how big it is, so the panel can
    say 'no data yet' instead of rendering an empty chart as though it were a
    measurement of zero."""
    path = os.path.join(_saleha_home(), filename)
    try:
        stat = os.stat(path)
        return {
            "path": path,
            "exists": True,
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        }
    except OSError:
        return {"path": path, "exists": False, "size_bytes": 0, "modified_at": None}


def runs(limit: int = 20) -> Dict[str, Any]:
    """Orchestrator run outcomes, recorded on every real run.

    ``MetricsTracker.summary()`` aggregates only the most recent 10,000 lines of
    metrics.jsonl, so the result is reported as recent activity rather than an
    all-time total.
    """
    from saleha.core.metrics import metrics_tracker

    summary = metrics_tracker.summary()
    recent = metrics_tracker.tail(limit=limit)
    return {
        "summary": summary,
        "summary_scope": "Aggregated from the most recent 10,000 recorded runs, not all time.",
        "recent": recent,
        "sources": {"metrics": _file_info("metrics.jsonl")},
    }


def audit(limit: int = 25) -> Dict[str, Any]:
    """Code-execution attempts, written by the executors on every attempt.

    This is the only real record of blocked executions: the approval gate and
    safety guard return their verdicts to the caller without persisting them, so
    denial counts have to come from here.
    """
    from saleha.core.audit_log import audit_log

    recent = audit_log.recent(limit)
    blocked = _audit_cache.get_or_compute("blocked", lambda: audit_log.blocked_entries())
    blocked_recent = blocked[-limit:] if blocked else []
    return {
        "recent": recent,
        "blocked_count": len(blocked),
        "blocked_recent": list(reversed(blocked_recent)),
        "sources": {"audit": _file_info("audit_log.jsonl")},
    }


def history(limit: int = 20) -> Dict[str, Any]:
    """Task records written by the team orchestrator."""
    from saleha.core.task_history import TaskHistory

    store = TaskHistory()
    recent = [_record_to_dict(r) for r in store.recent(limit)]
    failed = [_record_to_dict(r) for r in store.failed_tasks()]
    return {
        "recent": recent,
        "failed_count": len(failed),
        "failed_recent": failed[-limit:][::-1],
        "sources": {"history": _file_info("history.jsonl")},
    }


def _record_to_dict(record: Any) -> Dict[str, Any]:
    """TaskRecord is a dataclass in most builds, but fall back to attribute reads
    so a shape change here degrades to fewer fields rather than a 500."""
    for attr in ("to_dict", "_asdict"):
        converter = getattr(record, attr, None)
        if callable(converter):
            try:
                return converter()
            except Exception:
                break
    try:
        import dataclasses

        if dataclasses.is_dataclass(record):
            return dataclasses.asdict(record)
    except Exception:
        pass
    return {
        field: getattr(record, field, None)
        for field in ("timestamp", "goal", "model", "success", "attempts", "error")
    }


def models() -> Dict[str, Any]:
    """Per-model win rates recorded by the orchestrators.

    StatsTracker buckets its data by task type and exposes no public way to list
    the buckets, so the private store is read defensively: if its shape changes,
    the panel reports no model data rather than raising.
    """
    from saleha.core.stats_tracker import StatsTracker

    tracker = StatsTracker()
    raw = getattr(tracker, "_data", None)
    if not isinstance(raw, dict):
        return {
            "task_types": [],
            "unavailable_reason": "StatsTracker did not expose a readable bucket store.",
            "sources": {"stats": _file_info("stats.json")},
        }

    task_types: List[Dict[str, Any]] = []
    for task_type, bucket in raw.items():
        if not isinstance(bucket, dict):
            continue
        entries = []
        for model_name in bucket:
            try:
                stats = tracker.get_model_stats(model_name, task_type)
            except Exception:
                continue
            entries.append(
                {
                    "model": model_name,
                    "uses": getattr(stats, "uses", 0),
                    "successes": getattr(stats, "successes", 0),
                    "success_rate": getattr(stats, "success_rate", 0.0),
                    "avg_attempts": getattr(stats, "avg_attempts", 0.0),
                    "last_used": getattr(stats, "last_used", None),
                }
            )
        entries.sort(key=lambda e: e["uses"], reverse=True)
        best: Optional[str]
        try:
            best = tracker.best_model_for(task_type)
        except Exception:
            best = None
        task_types.append({"task_type": task_type, "best_model": best, "models": entries})

    task_types.sort(key=lambda t: sum(m["uses"] for m in t["models"]), reverse=True)
    return {"task_types": task_types, "sources": {"stats": _file_info("stats.json")}}


def overview() -> Dict[str, Any]:
    """Small combined payload for the panel's landing view.

    Every section degrades independently: if one source is unreadable the rest
    still render, and the failure is reported rather than shown as a zero.
    """
    from saleha import __version__
    from saleha.core.approval_gate import approval_gate

    sections: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    def section(name: str, compute):
        try:
            sections[name] = compute()
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"

    section("runs", lambda: runs(limit=5))
    section("audit", lambda: audit(limit=5))
    section("history", lambda: history(limit=5))

    approval_mode = None
    try:
        approval_mode = approval_gate.get_mode()
    except Exception as exc:
        errors["approval_mode"] = f"{type(exc).__name__}: {exc}"

    return {
        "version": __version__,
        "approval_mode": approval_mode,
        "sections": sections,
        "errors": errors,
        "excluded_sources": [
            {
                "name": "token_analytics",
                "reason": "Nothing in the product records invocations; the stored values are test fixtures.",
            },
            {
                "name": "hardware_accel",
                "reason": "Reports fixed constants rather than probing the machine.",
            },
            {
                "name": "workflow_dag",
                "reason": "Node statuses are a hardcoded literal, not live workflow state.",
            },
        ],
    }
