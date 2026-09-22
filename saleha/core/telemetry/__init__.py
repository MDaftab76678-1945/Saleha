"""
Saleha Core: Telemetry & Observability Subsystem (2026 Frontier Standard)

Provides OpenTelemetry-compatible hierarchical execution spans, token economics & ROI tracking,
append-only security audit logs, and performance metrics histograms:
- SessionTracer / session_tracer (Microsecond hierarchical execution span recorder)
- TokenAnalyticsEngine / token_analytics (Token consumption, reasoning overhead, & cloud ROI)
- AuditLog / audit_log (Tamper-evident execution audit logging)
- MetricsTracker / metrics_tracker (Throughput, success rates, & model performance metrics)
"""

from __future__ import annotations

from saleha.core.telemetry.audit_log import (
    AuditLog,
    audit_log,
)
from saleha.core.telemetry.metrics import (
    MetricsTracker,
    metrics_tracker,
)
from saleha.core.telemetry.session_tracer import (
    SessionTracer,
    TraceEvent,
    TraceSpan,
    session_tracer,
)
from saleha.core.telemetry.token_analytics import (
    InvocationRecord,
    TokenAnalyticsEngine,
    token_analytics,
)

from saleha.core.telemetry.hardware_profiler import (
    HardwareProfiler,
    HardwareSnapshot,
    get_profiler,
)
from saleha.core.telemetry.latency_histogram import (
    NanosecondLatencyHistogram,
)
from saleha.core.telemetry.performance_profiler import (
    PerformanceProfiler,
    ProfileMetrics,
    performance_profiler,
)
from saleha.core.telemetry.stats_tracker import (
    ModelStats,
    StatsTracker,
)
from saleha.core.telemetry.token_ledger import (
    LedgerEntry,
    TokenLedger,
    token_ledger,
)

__all__ = [
    "SessionTracer",
    "session_tracer",
    "TraceSpan",
    "TraceEvent",
    "TokenAnalyticsEngine",
    "token_analytics",
    "InvocationRecord",
    "AuditLog",
    "audit_log",
    "MetricsTracker",
    "metrics_tracker",
    "NanosecondLatencyHistogram",
    "StatsTracker",
    "ModelStats",
    "TokenLedger",
    "LedgerEntry",
    "token_ledger",
    "HardwareProfiler",
    "HardwareSnapshot",
    "get_profiler",
    "PerformanceProfiler",
    "ProfileMetrics",
    "performance_profiler",
]
