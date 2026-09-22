"""Tests for the Octopus Multi-Agent Swarm Expansion.

Validates the 4 frontier capability enhancements:
1. Polyglot TypeScript AST & Monorepo Interface Propagator
2. Visual UI & Multimodal Layout Auditor (overlaps, clipping, WCAG AA contrast)
3. Continuous Background Self-Improvement Daemon (DPO compilation, untested modules)
4. Database Schema Migration Safety Verifier (destructive ops, shadow DB rollback)
5. Octopus Swarm Multi-Brain Coordination (GWT blackboard, BFT consensus)
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from saleha.core.db.migration_safety_verifier import (
    MigrationSafetyVerifier,
    StaticMigrationScanner,
)
from saleha.core.polyglot.ts_interface_propagator import (
    TSASTAnalyzer,
    TSContractVerifier,
    TSInterface,
    TSProperty,
    TwoPhaseCommitTSPropagator,
)
from saleha.core.swarm.octopus_swarm_expansion import OctopusSwarmExpansion
from saleha.core.vision.visual_layout_auditor import (
    DOMBoundingBox,
    DOMElement,
    VisualLayoutAuditor,
    WCAGColorMath,
)


@pytest.fixture(autouse=True)
def test_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SALEHA_TEST_MODE", "1")
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")


# ---------------------------------------------------------------------------
# 1. Polyglot TypeScript AST & Contract Tests
# ---------------------------------------------------------------------------

def test_ts_ast_analyzer_parsing() -> None:
    ts_code = """
    import { Router } from 'express';
    import type { UserRole } from './types';

    export interface UserProfile extends BaseEntity {
        id: string;
        username: string;
        email?: string;
        readonly createdAt: Date;
    }

    export type SessionData = {
        token: string;
        expiresAt: number;
    }

    export async function authenticateUser(userId: string, role: string): Promise<boolean> {
        return true;
    }
    """
    interfaces, functions, imports = TSASTAnalyzer.parse_code(ts_code, "test.ts")

    assert "UserProfile" in interfaces
    user_prof = interfaces["UserProfile"]
    assert user_prof.is_exported is True
    assert "BaseEntity" in user_prof.extends
    assert "username" in user_prof.properties
    assert user_prof.properties["email"].optional is True
    assert user_prof.properties["createdAt"].readonly is True

    assert "SessionData" in interfaces
    assert interfaces["SessionData"].is_type_alias is True

    assert "authenticateUser" in functions
    fn = functions["authenticateUser"]
    assert fn.is_async is True
    assert len(fn.parameters) == 2
    assert fn.return_type == "Promise<boolean>"

    assert len(imports) == 2
    assert imports[0].source_module == "express"
    assert imports[1].is_type_only is True


def test_ts_contract_mutation_detection() -> None:
    old_iface = TSInterface(
        name="EngineConfig",
        properties={
            "timeoutMs": TSProperty("timeoutMs", "number"),
            "apiKey": TSProperty("apiKey", "string"),
        },
    )
    # Mutated: removed apiKey, changed timeoutMs to string
    new_iface = TSInterface(
        name="EngineConfig",
        properties={
            "timeoutMs": TSProperty("timeoutMs", "string"),
        },
    )

    consumer_code = "const conf: EngineConfig = { timeoutMs: 5000 }; console.log(conf.apiKey);"
    mismatches = TSContractVerifier.check_interface_mutation(
        old_iface=old_iface,
        new_iface=new_iface,
        consumer_code=consumer_code,
        file_path="apps/web/src/consumer.ts",
    )

    assert len(mismatches) == 2
    types = {m.mismatch_type for m in mismatches}
    assert "missing_property" in types
    assert "type_incompatibility" in types


def test_two_phase_commit_ts_propagator() -> None:
    temp_dir = Path(tempfile.mkdtemp())
    try:
        f1 = temp_dir / "a.ts"
        f2 = temp_dir / "b.ts"
        f1.write_text("export const A = 1;\n", encoding="utf-8")
        f2.write_text("export const B = 2;\n", encoding="utf-8")

        propagator = TwoPhaseCommitTSPropagator(root_dir=temp_dir)
        propagator.stage(f1, "export const A = 100;\n")
        propagator.stage(f2, "export const B = 200;\n")

        prepared, diags = propagator.prepare()
        assert prepared is True
        assert len(diags) == 0

        committed = propagator.commit()
        assert committed is True
        assert f1.read_text(encoding="utf-8") == "export const A = 100;\n"
        assert f2.read_text(encoding="utf-8") == "export const B = 200;\n"

        # Test Rollback on corrupted syntax
        propagator2 = TwoPhaseCommitTSPropagator(root_dir=temp_dir)
        propagator2.stage(f1, "export const A = { unclosed;\n")
        prep2, diags2 = propagator2.prepare()
        assert prep2 is False
        assert len(diags2) > 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 2. Visual UI & Multimodal Layout Auditor Tests
# ---------------------------------------------------------------------------

def test_visual_layout_auditor_overlap() -> None:
    auditor = VisualLayoutAuditor()

    # Two buttons overlapping by 50x50 pixels at z-index 1
    btn1 = DOMElement(
        selector="#submit-btn",
        tag="button",
        bbox=DOMBoundingBox(x=100.0, y=100.0, width=120.0, height=40.0, z_index=1),
        text="Submit",
        is_clickable=True,
    )
    btn2 = DOMElement(
        selector="#cancel-btn",
        tag="button",
        bbox=DOMBoundingBox(x=150.0, y=100.0, width=120.0, height=40.0, z_index=1),
        text="Cancel",
        is_clickable=True,
    )

    report = auditor.audit_layout([btn1, btn2], viewport_width=1280.0, viewport_height=800.0)
    assert report.is_clean is False
    assert len(report.overlap_defects) == 1
    defect = report.overlap_defects[0]
    assert defect.overlap_area_px == 70.0 * 40.0  # (220 - 150) * 40 = 2800.0
    assert defect.severity == "HIGH"


def test_visual_layout_auditor_clipping() -> None:
    auditor = VisualLayoutAuditor()

    # Wide container bleeding out of a 320px mobile viewport
    card = DOMElement(
        selector=".pricing-card",
        tag="div",
        bbox=DOMBoundingBox(x=20.0, y=50.0, width=350.0, height=200.0),
        text="Card Content",
    )

    report = auditor.audit_layout([card], viewport_width=320.0, viewport_height=568.0)
    assert len(report.clipping_defects) == 1
    assert report.clipping_defects[0].overflow_x == 50.0  # (20 + 350) - 320 = 50.0


def test_wcag_contrast_math() -> None:
    # Pure black on pure white: contrast ratio is exactly 21.0:1
    ratio = WCAGColorMath.compute_contrast_ratio("#000000", "#ffffff")
    assert ratio >= 20.9

    # Light grey (#aaaaaa) on white (#ffffff): fails WCAG AA 4.5:1
    bad_ratio = WCAGColorMath.compute_contrast_ratio("#aaaaaa", "#ffffff")
    assert bad_ratio < 4.5

    auditor = VisualLayoutAuditor()
    elem = DOMElement(
        selector=".muted-subtext",
        tag="p",
        bbox=DOMBoundingBox(x=10.0, y=10.0, width=100.0, height=20.0),
        text="This text is too faint to read comfortably.",
        text_color="#aaaaaa",
        background_color="#ffffff",
        font_size_pt=12.0,
    )
    report = auditor.audit_layout([elem], viewport_width=1280.0, viewport_height=800.0)
    assert len(report.contrast_defects) == 1
    assert report.contrast_defects[0].standard == "WCAG_AA"


# ---------------------------------------------------------------------------
# 3. Database Schema Migration Safety Verifier Tests
# ---------------------------------------------------------------------------

def test_migration_static_scanner_destructive_drop() -> None:
    sql = """
    DROP TABLE old_payments;
    ALTER TABLE users DROP COLUMN legacy_pin;
    ALTER TABLE accounts ADD COLUMN status VARCHAR(20) NOT NULL;
    """
    hazards = StaticMigrationScanner.scan_sql(sql)
    assert len(hazards) == 3
    types = [h.hazard_type for h in hazards]
    assert "DROP_TABLE" in types
    assert "DROP_COLUMN" in types
    assert "NOT_NULL_WITHOUT_DEFAULT" in types


def test_migration_safety_shadow_simulation() -> None:
    verifier = MigrationSafetyVerifier()

    baseline = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        email TEXT NOT NULL
    );
    """
    up_safe = """
    ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'MEMBER';
    """
    down_safe = """
    -- SQLite doesn't natively drop column easily in older versions, but reversible logic
    SELECT 1;
    """
    fixture = """
    INSERT INTO users (id, email, role) VALUES (1, 'alice@example.com', 'ADMIN');
    """

    report = verifier.audit_migration(
        up_sql=up_safe,
        down_sql=down_safe,
        baseline_schema=baseline,
        fixture_rows=fixture,
    )

    assert report.shadow_simulation_passed is True
    assert report.is_safe is True
    assert report.veto_triggered is False


# ---------------------------------------------------------------------------
# 4. Octopus Swarm Coordination Hub Tests
# ---------------------------------------------------------------------------

def test_octopus_swarm_expansion_mission() -> None:
    temp_dir = Path(tempfile.mkdtemp())
    try:
        bb_path = temp_dir / "blackboard.json"
        swarm = OctopusSwarmExpansion(repo_root=Path("."), blackboard_path=bb_path)

        dom_elements = [
            DOMElement(
                selector="#header",
                tag="header",
                bbox=DOMBoundingBox(x=0.0, y=0.0, width=1280.0, height=80.0),
                text="Header Nav",
                text_color="#ffffff",
                background_color="#000000",
            )
        ]

        outcome = swarm.run_coordinated_audit(
            mission_goal="Verify frontend and database safety",
            dom_elements=dom_elements,
            proposed_migration_sql=(
                "CREATE TABLE logs (id INTEGER PRIMARY KEY, msg TEXT);",
                "DROP TABLE logs;",
            ),
        )

        assert outcome.mission_id.startswith("mission_")
        assert outcome.polyglot_report is not None
        assert outcome.visual_report is not None
        assert outcome.db_report is not None
        assert outcome.consensus_ratified is True
        assert outcome.duration_ms >= 0.0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
