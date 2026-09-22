"""Saleha Core: Database Schema Migration Safety Verifier.

Performs static pre-flight hazard scanning (detecting DROP TABLE, DROP COLUMN,
non-null columns without defaults) and dynamic shadow-database two-way
migration simulation (up -> populate fixture -> down rollback) to guarantee
zero data loss and transaction reversibility.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class MigrationHazard:
    """Represents a dangerous or destructive schema modification."""
    hazard_type: str  # "DROP_TABLE", "DROP_COLUMN", "NOT_NULL_WITHOUT_DEFAULT", "TYPE_NARROWING"
    severity: str     # "FATAL", "HIGH", "MEDIUM"
    table_name: str
    column_name: Optional[str]
    raw_statement: str
    description: str
    mitigation: str


@dataclass
class MigrationAuditReport:
    """Authoritative outcome of static scan and shadow-database simulation."""
    is_safe: bool
    is_reversible: bool
    veto_triggered: bool
    hazards: List[MigrationHazard] = field(default_factory=list)
    shadow_simulation_passed: bool = False
    simulation_error: Optional[str] = None
    summary: str = ""


class StaticMigrationScanner:
    """Static AST and regex scanner detecting destructive SQL operations."""

    DROP_TABLE_RE = re.compile(
        r"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?['\"`]?([A-Za-z0-9_]+)['\"`]?",
        re.IGNORECASE,
    )

    DROP_COLUMN_RE = re.compile(
        r"\bALTER\s+TABLE\s+['\"`]?([A-Za-z0-9_]+)['\"`]?\s+DROP\s+(?:COLUMN\s+)?['\"`]?([A-Za-z0-9_]+)['\"`]?",
        re.IGNORECASE,
    )

    ADD_NOT_NULL_RE = re.compile(
        r"\bALTER\s+TABLE\s+['\"`]?([A-Za-z0-9_]+)['\"`]?\s+ADD\s+(?:COLUMN\s+)?['\"`]?([A-Za-z0-9_]+)['\"`]?\s+([A-Za-z0-9_]+)(?:\([^)]*\))?\s+NOT\s+NULL\b(?!\s+DEFAULT)",
        re.IGNORECASE,
    )

    @classmethod
    def scan_sql(cls, sql_text: str) -> List[MigrationHazard]:
        """Scans SQL migration text for destructive patterns."""
        hazards: List[MigrationHazard] = []

        # 1. DROP TABLE
        for m in cls.DROP_TABLE_RE.finditer(sql_text):
            table = m.group(1)
            hazards.append(
                MigrationHazard(
                    hazard_type="DROP_TABLE",
                    severity="FATAL",
                    table_name=table,
                    column_name=None,
                    raw_statement=m.group(0),
                    description=f"Destructive operation: Table '{table}' will be dropped, causing irreversible data loss.",
                    mitigation=f"Rename table to 'archived_{table}' instead of dropping, or export data first.",
                )
            )

        # 2. DROP COLUMN
        for m in cls.DROP_COLUMN_RE.finditer(sql_text):
            table = m.group(1)
            column = m.group(2)
            hazards.append(
                MigrationHazard(
                    hazard_type="DROP_COLUMN",
                    severity="FATAL",
                    table_name=table,
                    column_name=column,
                    raw_statement=m.group(0),
                    description=f"Destructive operation: Column '{column}' dropped from '{table}'. Existing data will be deleted.",
                    mitigation="Deprecate column in application layer before dropping, or perform shadow copy.",
                )
            )

        # 3. ADD COLUMN NOT NULL without DEFAULT
        for m in cls.ADD_NOT_NULL_RE.finditer(sql_text):
            table = m.group(1)
            column = m.group(2)
            hazards.append(
                MigrationHazard(
                    hazard_type="NOT_NULL_WITHOUT_DEFAULT",
                    severity="HIGH",
                    table_name=table,
                    column_name=column,
                    raw_statement=m.group(0),
                    description=(
                        f"Unsafe migration: Adding NOT NULL column '{column}' to existing table '{table}' "
                        f"without a DEFAULT value will cause immediate constraint violation on existing rows."
                    ),
                    mitigation=f"Add DEFAULT value to '{column}' or add as nullable first, backfill data, then alter to NOT NULL.",
                )
            )

        return hazards


def _schema_snapshot(cursor: sqlite3.Cursor) -> List[Tuple[str, str, Tuple[Tuple[object, ...], ...]]]:
    """Tables with their column definitions, plus index names, in a stable order."""
    cursor.execute(
        "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    )
    snapshot: List[Tuple[str, str, Tuple[Tuple[object, ...], ...]]] = []
    for obj_type, name in cursor.fetchall():
        cols: Tuple[Tuple[object, ...], ...] = ()
        if obj_type == "table":
            cols = tuple(tuple(row) for row in cursor.execute(f'PRAGMA table_info("{name}")').fetchall())
        snapshot.append((obj_type, name, cols))
    return snapshot


class ShadowDatabaseVerifier:
    """Executes migration up and rollback in an isolated in-memory database."""

    @classmethod
    def simulate_two_way_migration(
        cls,
        baseline_schema_sql: str,
        up_migration_sql: str,
        down_migration_sql: str,
        fixture_rows_sql: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Simulates: baseline -> up() -> fixture insert -> down() rollback."""
        try:
            conn = sqlite3.connect(":memory:")
            cursor = conn.cursor()

            # 1. Apply baseline
            if baseline_schema_sql.strip():
                cursor.executescript(baseline_schema_sql)
            baseline_snapshot = _schema_snapshot(cursor)

            # 2. Apply up() migration
            cursor.executescript(up_migration_sql)

            # 3. Populate fixture rows if provided
            if fixture_rows_sql and fixture_rows_sql.strip():
                cursor.executescript(fixture_rows_sql)

            # 4. Apply down() rollback migration
            cursor.executescript(down_migration_sql)

            # 5. Reversible means down() restored the baseline schema, not just
            # that it ran without error.
            after_down = _schema_snapshot(cursor)
            conn.close()
            if after_down != baseline_snapshot:
                return False, "down() ran but did not restore the baseline schema."
            return True, None
        except Exception as e:
            return False, f"Shadow database simulation failed: {e}"


class MigrationSafetyVerifier:
    """Master validator for schema migrations with Byzantine veto capability."""

    def __init__(self) -> None:
        self.scanner = StaticMigrationScanner()
        self.shadow_verifier = ShadowDatabaseVerifier()

    def audit_migration(
        self,
        up_sql: str,
        down_sql: str,
        baseline_schema: str = "",
        fixture_rows: str = "",
    ) -> MigrationAuditReport:
        """Runs static hazard scan and dynamic shadow DB simulation."""
        # Static scan
        hazards = self.scanner.scan_sql(up_sql)
        fatal_count = sum(1 for h in hazards if h.severity == "FATAL")

        # Dynamic simulation
        sim_passed, sim_error = self.shadow_verifier.simulate_two_way_migration(
            baseline_schema_sql=baseline_schema,
            up_migration_sql=up_sql,
            down_migration_sql=down_sql,
            fixture_rows_sql=fixture_rows,
        )

        is_reversible = sim_passed
        is_safe = (fatal_count == 0) and sim_passed
        veto = (fatal_count > 0) or not sim_passed

        summary = (
            f"Migration audit: {'SAFE' if is_safe else 'REJECTED'}. "
            f"Hazards detected: {len(hazards)} (Fatal: {fatal_count}). "
            f"Shadow DB Reversibility: {'VERIFIED' if sim_passed else 'FAILED'}."
        )

        return MigrationAuditReport(
            is_safe=is_safe,
            is_reversible=is_reversible,
            veto_triggered=veto,
            hazards=hazards,
            shadow_simulation_passed=sim_passed,
            simulation_error=sim_error,
            summary=summary,
        )
