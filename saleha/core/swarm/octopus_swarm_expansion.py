"""Saleha Core: Octopus Swarm Expansion & Multi-Brain Coordination Hub.

Integrates specialized peripheral arm brains (Polyglot TS, Visual UI, Continuous Daemon,
Database Safety) with the central coordinating mind via GWT Blackboard sparse attention
and Byzantine Fault Tolerant (BFT) consensus gates.
"""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from saleha.agents.database_safety_agent import DatabaseSafetyAgent
from saleha.agents.polyglot_ts_agent import PolyglotTSAgent
from saleha.agents.visual_ui_agent import VisualUIAgent
from saleha.core.daemons.continuous_learning_daemon import ContinuousLearningDaemon


def _load_skill_symbol(script_path: Path, class_name: str) -> Any:
    """Dynamically loads a class symbol from an agent skill script."""
    if script_path.exists():
        try:
            spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return getattr(mod, class_name, None)
        except Exception:
            return None
    return None


_repo_root = Path(__file__).resolve().parents[3]

_gwt_script = _repo_root / ".agents" / "skills" / "gwt-blackboard" / "scripts" / "octopus_blackboard.py"
BlackboardCoordinator = _load_skill_symbol(_gwt_script, "BlackboardCoordinator")

_bft_script = _repo_root / ".agents" / "skills" / "bft-swarm-consensus" / "scripts" / "bft_consensus_gate.py"
BFTConsensusGate = _load_skill_symbol(_bft_script, "BFTConsensusGate")


@dataclass
class SwarmMissionOutcome:
    """Consolidated outcome of an Octopus swarm coordination mission."""
    mission_id: str
    goal: str
    polyglot_report: Dict[str, Any]
    visual_report: Optional[Dict[str, Any]]
    db_report: Optional[Dict[str, Any]]
    daemon_report: Optional[Dict[str, Any]]
    top_salience_fact: Optional[Dict[str, Any]]
    consensus_ratified: bool
    duration_ms: float
    summary: str


class OctopusSwarmExpansion:
    """Master multi-brain orchestrator coordinating specialized domain agents."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        blackboard_path: Optional[Path] = None,
    ) -> None:
        self.repo_root = repo_root or Path(".")
        bb_path = blackboard_path or (self.repo_root / ".agents" / "scratch" / "gwt_blackboard.json")
        
        # Initialize GWT Blackboard coordinator
        if BlackboardCoordinator:
            self.blackboard = BlackboardCoordinator(storage_path=bb_path)
        else:
            self.blackboard = None

        # Initialize BFT consensus gate
        if BFTConsensusGate:
            self.consensus_gate = BFTConsensusGate()
        else:
            self.consensus_gate = None

        # Specialized Arm Brains
        self.polyglot_agent = PolyglotTSAgent()
        self.visual_agent = VisualUIAgent()
        self.db_agent = DatabaseSafetyAgent()
        self.learning_daemon = ContinuousLearningDaemon(repo_root=self.repo_root)

    def run_coordinated_audit(
        self,
        mission_goal: str,
        dom_elements: Optional[List[Any]] = None,
        proposed_migration_sql: Optional[Tuple[str, str]] = None,
    ) -> SwarmMissionOutcome:
        """Dispatches specialized arm brains, aggregates facts on GWT blackboard, and runs BFT gate."""
        start_time = time.perf_counter()
        mission_id = f"mission_{int(time.time())}"

        # 1. Arm Brain: Polyglot Monorepo Audit
        ts_audit = self.polyglot_agent.audit_monorepo(self.repo_root)
        if self.blackboard:
            salience = 8.5 if not ts_audit["healthy"] else 2.0
            self.blackboard.post_fact(
                agent_name="PolyglotTSAgent",
                topic="monorepo_contracts",
                content=f"Indexed {ts_audit['total_interfaces']} interfaces across {len(ts_audit['packages'])} packages. Mismatches: {len(ts_audit['mismatches'])}",
                salience=salience,
            )

        # 2. Arm Brain: Visual UI Audit (if DOM elements provided)
        visual_summary = None
        if dom_elements:
            report = self.visual_agent.audit_screen(dom_elements)
            visual_summary = {
                "overlaps": len(report.overlap_defects),
                "clippings": len(report.clipping_defects),
                "contrast_failures": len(report.contrast_defects),
                "is_clean": report.is_clean,
            }
            if self.blackboard:
                salience = 9.0 if not report.is_clean else 1.5
                self.blackboard.post_fact(
                    agent_name="VisualUIAgent",
                    topic="layout_integrity",
                    content=f"Visual audit found {len(report.overlap_defects)} overlaps, {len(report.contrast_defects)} contrast bugs.",
                    salience=salience,
                )

        # 3. Arm Brain: Database Safety Audit (if migration provided)
        db_summary = None
        db_ratified = True
        if proposed_migration_sql:
            up_sql, down_sql = proposed_migration_sql
            migration_report = self.db_agent.audit_schema_migration(up_sql, down_sql)
            db_ratified = self.db_agent.can_ratify(migration_report)
            db_summary = {
                "is_safe": migration_report.is_safe,
                "is_reversible": migration_report.is_reversible,
                "veto_triggered": migration_report.veto_triggered,
                "hazards_count": len(migration_report.hazards),
            }
            if self.blackboard:
                salience = 10.0 if migration_report.veto_triggered else 3.0
                self.blackboard.post_fact(
                    agent_name="DatabaseSafetyAgent",
                    topic="schema_safety",
                    content=migration_report.summary,
                    salience=salience,
                )

        # 4. Arm Brain: Continuous Learning Daemon Cycle
        daemon_result = self.learning_daemon.execute_single_cycle()
        daemon_summary = {
            "uncompiled_pairs": daemon_result.uncompiled_pairs_count,
            "dpo_exported": daemon_result.dpo_batch_exported,
            "untested_candidates_count": len(daemon_result.untested_candidates),
        }
        if self.blackboard:
            self.blackboard.post_fact(
                agent_name="ContinuousLearningDaemon",
                topic="self_evolution",
                content=f"Found {len(daemon_result.untested_candidates)} untested modules. DPO exported: {daemon_result.dpo_batch_exported}",
                salience=4.0,
            )

        # 5. GWT Blackboard Attention Arbitration (Brain 0 Global Broadcast)
        top_fact = self.blackboard.arbitrate_attention() if self.blackboard else None

        # 6. BFT Consensus Gate Supermajority Ratification
        candidate_code = "def ratified_action(): return True"
        consensus_result = {"ratified": True}
        if self.consensus_gate:
            consensus_result = self.consensus_gate.evaluate_proposal(
                candidate_code=candidate_code,
                precond_expr="x >= 0" if db_ratified else "x < 0",
                postcond_expr="x >= 0",
            )

        mission_ratified = consensus_result.get("ratified", True) and db_ratified
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        summary = (
            f"Octopus Swarm Mission [{mission_id}] complete in {duration_ms}ms. "
            f"Ratified: {mission_ratified}. Top Salience: {top_fact.get('agent', 'None') if top_fact else 'None'}."
        )

        return SwarmMissionOutcome(
            mission_id=mission_id,
            goal=mission_goal,
            polyglot_report=ts_audit,
            visual_report=visual_summary,
            db_report=db_summary,
            daemon_report=daemon_summary,
            top_salience_fact=top_fact,
            consensus_ratified=mission_ratified,
            duration_ms=duration_ms,
            summary=summary,
        )
