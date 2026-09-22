"""Saleha Agents: Polyglot TypeScript Monorepo Specialist Agent.

Specialized autonomous agent responsible for TypeScript AST analysis,
monorepo cross-package interface contracts, ESM import propagation, and
type-safe refactoring.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from saleha.agents.base_agent import BaseAgent
from saleha.core.polyglot.ts_interface_propagator import (
    TSContractMismatch,
    TSContractVerifier,
    TSMonorepoDAG,
    TwoPhaseCommitTSPropagator,
)


class PolyglotTSAgent(BaseAgent):
    """Specialized arm brain for TypeScript and JavaScript monorepo management."""

    def __init__(
        self,
        model: str = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(role="polyglot_ts", model=model, **kwargs)
        self.propagator = TwoPhaseCommitTSPropagator()

    def audit_monorepo(self, root_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Audits TypeScript packages for broken interfaces and unlinked dependencies."""
        root = root_dir or self.pc.workspace_root
        dag = TSMonorepoDAG(root)
        dag.index_all()

        total_interfaces = sum(len(ifaces) for ifaces in dag.package_interfaces.values())
        total_functions = sum(len(funcs) for funcs in dag.package_functions.values())
        total_imports = sum(len(imps) for imps in dag.package_imports.values())

        # Check contracts across packages
        mismatches: List[TSContractMismatch] = []
        for pkg_name, imps in dag.package_imports.items():
            for imp in imps:
                # If importing from another monorepo package
                for prod_name, prod_ifaces in dag.package_interfaces.items():
                    if prod_name in imp.source_module:
                        prod_funcs = dag.package_functions.get(prod_name, {})
                        issues = TSContractVerifier.verify_contracts(
                            producer_interfaces=prod_ifaces,
                            producer_functions=prod_funcs,
                            consumer_imports=[imp],
                            consumer_source_code={},
                            producer_name=prod_name,
                            consumer_name=pkg_name,
                        )
                        mismatches.extend(issues)

        # Log audit action to AgentPC flight recorder
        self.pc.blackbox.record(
            event_type="POLYGLOT_TS_AUDIT",
            stage="AUDIT_MONOREPO",
            payload={
                "packages_discovered": list(dag.packages.keys()),
                "interfaces_count": total_interfaces,
                "functions_count": total_functions,
                "imports_count": total_imports,
                "mismatches_found": len(mismatches),
            },
        )

        return {
            "packages": list(dag.packages.keys()),
            "total_interfaces": total_interfaces,
            "total_functions": total_functions,
            "total_imports": total_imports,
            "mismatches": mismatches,
            "healthy": len(mismatches) == 0,
        }

    def propagate_change_safely(
        self,
        staged_files: Dict[Path, str],
    ) -> Tuple[bool, List[str]]:
        """Atomically validates and commits TypeScript changes across multiple files."""
        propagator = TwoPhaseCommitTSPropagator()
        for p, content in staged_files.items():
            propagator.stage(p, content)

        prepared, diagnostics = propagator.prepare()
        if not prepared:
            self.pc.blackbox.record(
                event_type="2PC_PREPARE_REJECTED",
                stage="PREPARE",
                payload={"diagnostics": diagnostics},
                status="FAIL",
            )
            return False, diagnostics

        committed = propagator.commit()
        if committed:
            self.pc.blackbox.record(
                event_type="2PC_COMMIT_SUCCESS",
                stage="COMMIT",
                payload={"modified_files": [str(p) for p in staged_files]},
                status="PASS",
            )
            return True, []
        else:
            self.pc.blackbox.record(
                event_type="2PC_COMMIT_FAILED_ROLLBACK",
                stage="COMMIT",
                payload={"files": [str(p) for p in staged_files]},
                status="FAIL",
            )
            return False, ["Two-phase commit failed during disk write. Rolled back."]
