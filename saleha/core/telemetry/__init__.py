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

from saleha.core.session_tracer import (
    SessionTracer,
    session_tracer,
    TraceSpan,
    TraceEvent,
)
from saleha.core.token_analytics import (
    TokenAnalyticsEngine,
    token_analytics,
    InvocationRecord,
)
from saleha.core.audit_log import (
    AuditLog,
    audit_log,
)
from saleha.core.metrics import (
    MetricsTracker,
    metrics_tracker,
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
]
