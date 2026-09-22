"""Saleha Agents: Database Migration Safety Agent.

Specialized autonomous agent responsible for auditing database migrations,
detecting destructive schema alterations, verifying shadow-database reversibility,
and enforcing Byzantine vetoes against data loss.
"""

from __future__ import annotations

from typing import Any

from saleha.agents.base_agent import BaseAgent
from saleha.core.db.migration_safety_verifier import (
    MigrationAuditReport,
    MigrationSafetyVerifier,
)


class DatabaseSafetyAgent(BaseAgent):
    """Specialized arm brain for database schema integrity and migration safety."""

    def __init__(
        self,
        model: str = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(role="database_safety", model=model, **kwargs)
        self.verifier = MigrationSafetyVerifier()

    def audit_schema_migration(
        self,
        up_sql: str,
        down_sql: str,
        baseline_schema: str = "",
        fixture_rows: str = "",
    ) -> MigrationAuditReport:
        """Audits proposed database migration for safety and reversibility."""
        report = self.verifier.audit_migration(
            up_sql=up_sql,
            down_sql=down_sql,
            baseline_schema=baseline_schema,
            fixture_rows=fixture_rows,
        )

        # Record in AgentPC blackbox
        self.pc.blackbox.record(
            event_type="DB_MIGRATION_AUDIT",
            stage="AUDIT_SCHEMA",
            payload={
                "is_safe": report.is_safe,
                "is_reversible": report.is_reversible,
                "veto_triggered": report.veto_triggered,
                "hazards_count": len(report.hazards),
                "summary": report.summary,
            },
        )

        return report

    def can_ratify(self, report: MigrationAuditReport) -> bool:
        """Byzantine veto gate: only ratifies if zero fatal hazards and reversibility proved."""
        return report.is_safe and not report.veto_triggered
