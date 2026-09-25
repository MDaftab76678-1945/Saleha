"""
Saleha Core: The Octopus Multi-Brain Coordination Engine (Step 3 Master Vision)

Architectural Philosophy:
"An octopus has nine brains. This system operates just like an octopus -- each arm
has its own specialized brain, governed by a central coordinating mind."

Topological Structure:
- 1 Central Coordinating Mind (Brain 0): Executive intent, Synaptic Blackboard,
  conflict resolution, and unified synthesis.
- 8 Specialized Peripheral Arm Brains:
  1. Planner Brain: Goal breakdown & dependency sequencing
  2. Architect Brain: System architecture, ADR, component contracts
  3. Coder Brain: Multi-language code synthesis & smart patching
  4. Security Brain: AST danger checks, CWE vulnerability audit & hardening
  5. QA Brain: Invariant assertion suite & physical sandbox execution
  6. SRE Brain: Chaos fault-tolerance, circuit breakers, and error budgets
  7. Critic Brain: Peer review, quality scoring, and constitutional compliance
  8. ToolForge Brain: On-the-fly autonomous tool synthesis & registry discovery
"""

from __future__ import annotations

import contextlib
import enum
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from saleha.core.swarm.agent_message_bus import (
    AgentMessageBus,
    OctopusBrainCompletedEvent,
    OctopusBrainDispatchedEvent,
    OctopusConflictResolvedEvent,
    OctopusSynthesisCompletedEvent,
)
from saleha.core.swarm.agent_message_bus import (
    message_bus as global_message_bus,
)
from saleha.core.swarm.agent_worker_pool import (
    AgentWorkerPool,
    WorkerTaskResult,
)
from saleha.core.swarm.agent_worker_pool import (
    worker_pool as global_worker_pool,
)


class ArmBrainRole(str, enum.Enum):
    """The 8 specialized peripheral arm brains of the Octopus system."""
    PLANNER = "planner"
    ARCHITECT = "architect"
    CODER = "coder"
    SECURITY = "security"
    QA = "qa"
    SRE = "sre"
    CRITIC = "critic"
    TOOLFORGE = "toolforge"


@dataclass
class ArmBrainOutput:
    """Output recorded from one peripheral arm brain."""
    brain_role: str
    brain_name: str
    status: str  # "success", "failed", "skipped"
    summary: str
    payload: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: Optional[str] = None


class SynapticBlackboard:
    """Thread-safe shared memory repository across all 9 brains."""

    def __init__(self, goal: str) -> None:
        self.lock = threading.Lock()
        self.goal: str = goal
        self.plan_steps: List[str] = []
        self.adr_title: str = ""
        self.architecture_components: List[str] = []
        self.system_design_md: str = ""
        self.source_code: str = ""
        self.code_generated: bool = False
        self.forged_tools: List[str] = []
        # Every verdict starts as "not done". These used to start True (and
        # resilience at 100.0), so an arm that crashed or timed out left
        # "clean / passed / approved / 100%" behind and the run succeeded.
        self.security_checked: bool = False
        self.security_clean: bool = False
        self.hardened_code_suggestion: str = ""
        self.vulnerabilities: List[str] = []
        self.test_code: str = ""
        self.tests_ran: bool = False
        self.tests_passed: bool = False
        self.test_count: int = 0
        self.test_error: str = ""
        self.resilience_score: Optional[float] = None  # None: not measured
        self.circuit_breaker_patch: str = ""
        self.review_ran: bool = False
        self.review_approved: bool = False
        self.review_feedback: str = ""
        self.conflicts: List[str] = []
        self.brain_outputs: Dict[str, ArmBrainOutput] = {}

    def record_brain_output(self, output: ArmBrainOutput) -> None:
        with self.lock:
            self.brain_outputs[output.brain_role] = output


@dataclass
class OctopusExecutionResult:
    """Authoritative outcome of a complete 9-brain Octopus coordination run."""
    execution_id: str
    goal: str
    success: bool
    final_code: str
    adr_title: str
    security_clean: bool
    tests_passed: bool
    resilience_score: Optional[float]  # None: not measured (no fault injection exists)
    review_approved: bool
    total_duration_ms: float
    brain_outputs: Dict[str, ArmBrainOutput]
    summary_report: str
    code_generated: bool = False
    tests_ran: bool = False
    security_checked: bool = False


class OctopusCoordinator:
    """Central Coordinating Mind (Brain 0) orchestrating 8 specialized peripheral brains."""

    def __init__(
        self,
        model: str = "auto",
        worker_pool: Optional[AgentWorkerPool] = None,
        bus: Optional[AgentMessageBus] = None,
        timeout_sec: float = 120.0,
        use_supremacy: bool = False,
    ) -> None:
        self.model = model
        self.worker_pool = worker_pool or global_worker_pool
        self.bus = bus or global_message_bus
        self.timeout_sec = timeout_sec
        self.use_supremacy = use_supremacy

    def _resolve_model(self, task_role: str) -> str:
        if os.environ.get("SALEHA_TEST_MODE") == "1" or self.model == "mock":
            return "mock"
        if self.model and self.model != "auto":
            return self.model
        try:
            from saleha.core.platform.smart_router import smart_router
            return smart_router.select_model_for_task(task_role)
        except Exception:
            return "auto"

    def coordinate(
        self,
        goal: str,
        execution_id: Optional[str] = None,
        callback: Optional[Callable[[ArmBrainOutput], None]] = None,
    ) -> OctopusExecutionResult:
        """Executes full multi-brain coordination mission through structured phases."""
        exec_id = execution_id or str(uuid.uuid4())[:8]
        start_time = time.perf_counter()
        blackboard = SynapticBlackboard(goal=goal)

        # Pre-warm agent imports in main thread to prevent Python 3.14 import lock deadlock
        from saleha.agents.architect import ArchitectAgent
        from saleha.agents.chaos_resilience import ChaosResilienceAgent
        from saleha.agents.coder import CoderAgent
        from saleha.agents.planner import PlannerAgent
        from saleha.agents.qa_lead import QALeadAgent
        from saleha.agents.reviewer import ReviewerAgent
        from saleha.agents.security_guard import SecurityGuardAgent

        # Notify dispatch of Brain 0 (Central Mind)
        self.bus.publish(
            OctopusBrainDispatchedEvent(
                sender_agent="CentralMind",
                brain_role="central_mind",
                mission=f"Octopus Mission [{exec_id}]: {goal}",
            )
        )

        def _dispatch_and_record(
            role: ArmBrainRole,
            name: str,
            runner_fn: Callable[[], Tuple[str, Dict[str, Any]]],
        ) -> ArmBrainOutput:
            b_start = time.perf_counter()
            self.bus.publish(
                OctopusBrainDispatchedEvent(
                    sender_agent="CentralMind",
                    brain_role=role.value,
                    mission=f"Executing {name}",
                )
            )
            try:
                summary, payload = runner_fn()
                dur_ms = round((time.perf_counter() - b_start) * 1000, 2)
                out = ArmBrainOutput(
                    brain_role=role.value,
                    brain_name=name,
                    status="success",
                    summary=summary,
                    payload=payload,
                    duration_ms=dur_ms,
                )
            except Exception as exc:
                dur_ms = round((time.perf_counter() - b_start) * 1000, 2)
                out = ArmBrainOutput(
                    brain_role=role.value,
                    brain_name=name,
                    status="failed",
                    summary=f"Error executing {name}: {exc}",
                    duration_ms=dur_ms,
                    error=str(exc),
                )

            blackboard.record_brain_output(out)
            self.bus.publish(
                OctopusBrainCompletedEvent(
                    sender_agent=name,
                    brain_role=role.value,
                    status=out.status,
                    duration_ms=out.duration_ms,
                    summary=out.summary,
                )
            )
            if callback:
                with contextlib.suppress(Exception):
                    callback(out)
            return out

        # =====================================================================
        # PHASE 1: STRATEGY & INVARIANTS (Arms 1 & 2 run concurrently)
        # =====================================================================
        def _run_planner() -> Tuple[str, Dict[str, Any]]:
            planner = PlannerAgent(model=self._resolve_model("planner"))
            plan_res = planner.create_plan(goal)
            if not plan_res.success:
                # No plan is not a failure of the run (the coder can work from
                # the goal), but it must not be reported as a structured plan.
                with blackboard.lock:
                    blackboard.plan_steps = []
                return "No plan generated; coding from the goal alone", {"steps": [], "planned": False}
            with blackboard.lock:
                blackboard.plan_steps = plan_res.steps
            return f"Structured {len(plan_res.steps)} plan step(s)", {"steps": plan_res.steps, "planned": True}

        def _run_architect() -> Tuple[str, Dict[str, Any]]:
            architect = ArchitectAgent(model=self._resolve_model("architect"))
            design = architect.design_system(goal)
            with blackboard.lock:
                blackboard.adr_title = design.adr_title
                blackboard.architecture_components = design.components
                blackboard.system_design_md = design.system_design_md
            return (
                f"Generated ADR '{design.adr_title}' ({design.pattern}) with {len(design.components)} component(s)",
                {
                    "adr_title": design.adr_title,
                    "pattern": design.pattern,
                    "components": design.components,
                },
            )

        parallel_phase1 = [
            ("arm_planner", _run_planner, (), {}),
            ("arm_architect", _run_architect, (), {}),
        ]
        p1_res = self.worker_pool.execute_parallel(parallel_phase1, timeout_sec=self.timeout_sec)
        for task_id, role, name, _func in [
            ("arm_planner", ArmBrainRole.PLANNER, "PlannerBrain", _run_planner),
            ("arm_architect", ArmBrainRole.ARCHITECT, "ArchitectBrain", _run_architect),
        ]:
            tres: WorkerTaskResult = p1_res.get(task_id, WorkerTaskResult(success=False, error_message="Task dropped"))
            if not tres.success:
                out = ArmBrainOutput(
                    brain_role=role.value,
                    brain_name=name,
                    status="failed",
                    summary=tres.error_message or "Timeout",
                    duration_ms=tres.execution_time_ms,
                    error=tres.error_message,
                )
                blackboard.record_brain_output(out)
                if callback:
                    callback(out)
            else:
                summary, payload = tres.result
                out = ArmBrainOutput(
                    brain_role=role.value,
                    brain_name=name,
                    status="success",
                    summary=summary,
                    payload=payload,
                    duration_ms=tres.execution_time_ms,
                )
                blackboard.record_brain_output(out)
                self.bus.publish(
                    OctopusBrainCompletedEvent(
                        sender_agent=name,
                        brain_role=role.value,
                        status="success",
                        duration_ms=tres.execution_time_ms,
                        summary=summary,
                    )
                )
                if callback:
                    callback(out)

        # =====================================================================
        # PHASE 2: IMPLEMENTATION & TOOLING (Arms 3 & 8)
        # =====================================================================
        def _run_coder() -> Tuple[str, Dict[str, Any]]:
            if self.use_supremacy:
                from saleha.core.local_supremacy import LocalSupremacyEngine
                sup_engine = LocalSupremacyEngine(
                    model=self._resolve_model("coder"),
                    num_trajectories=4,
                    max_refinements=2,
                )
                sup_res = sup_engine.solve(
                    problem=f"{goal}\nContext: Plan: {blackboard.plan_steps}\nComponents: {blackboard.architecture_components}",
                    test_suite="",
                )
                code = sup_res.winner_code or ""
                if not code.strip():
                    raise RuntimeError("Local Supremacy produced no code")
                with blackboard.lock:
                    blackboard.source_code = code
                    blackboard.code_generated = True
                strat = sup_res.winner_strategy or "supremacy"
                return (
                    f"Synthesized via Local Supremacy [{strat}] (amp: {sup_res.amplification_factor}x, {len(code)} chars)",
                    {
                        "code": code,
                        "strategy": strat,
                        "amplification_factor": sup_res.amplification_factor,
                        "reflexion_repairs": len(sup_res.repairs),
                        "candidates_evaluated": len(sup_res.candidates),
                    },
                )

            coder = CoderAgent(model=self._resolve_model("coder"))
            context_hint = f"Plan: {blackboard.plan_steps}\nComponents: {blackboard.architecture_components}"
            res = coder.generate_code(f"{goal}\nContext: {context_hint}")
            if not res.success or not res.code.strip():
                # This used to substitute `def execute(): return True`, which
                # every later arm then "verified".
                raise RuntimeError(f"no code generated: {res.error or 'empty model output'}")
            with blackboard.lock:
                blackboard.source_code = res.code
                blackboard.code_generated = True
            return f"Generated code ({len(res.code)} chars)", {"code": res.code}

        def _run_toolforge() -> Tuple[str, Dict[str, Any]]:
            from saleha.tools.base import tool_registry
            tool_registry.auto_discover()
            tools_available = tool_registry.list_tools()
            with blackboard.lock:
                blackboard.forged_tools = [t.name for t in tools_available]
            return (
                f"Discovered {len(tools_available)} registered dynamic tool(s) in catalog",
                {"tools": [t.name for t in tools_available]},
            )

        _dispatch_and_record(ArmBrainRole.CODER, "CoderBrain", _run_coder)
        _dispatch_and_record(ArmBrainRole.TOOLFORGE, "ToolForgeBrain", _run_toolforge)

        # =====================================================================
        # PHASE 3: CONCURRENT TRI-DIMENSIONAL VERIFICATION (Arms 4, 5, 6)
        # =====================================================================
        # Security and QA check this exact text, and it stays the final code:
        # the Security arm used to swap in its regex patch while QA ran on
        # the unpatched code in parallel, so the returned code was not the
        # code that was tested. The patch is now only a suggestion.
        current_code = blackboard.source_code

        def _require_code() -> None:
            if not current_code.strip():
                raise RuntimeError("skipped: no generated code to check")

        def _run_security() -> Tuple[str, Dict[str, Any]]:
            _require_code()
            sec_agent = SecurityGuardAgent(model=self._resolve_model("security"))
            audit = sec_agent.audit_and_harden(goal, current_code)
            with blackboard.lock:
                blackboard.security_checked = True
                blackboard.security_clean = audit.is_secure
                blackboard.vulnerabilities = audit.vulnerabilities_found
                if not audit.is_secure and audit.hardened_code != current_code:
                    blackboard.hardened_code_suggestion = audit.hardened_code
                    blackboard.conflicts.append("Security arm suggested an untested auto-patch")
            status_text = "clean" if audit.is_secure else f"{len(audit.vulnerabilities_found)} issue(s) found"
            return f"Security scan: {status_text}", {
                "is_secure": audit.is_secure,
                "vulnerabilities": audit.vulnerabilities_found,
            }

        def _run_qa() -> Tuple[str, Dict[str, Any]]:
            _require_code()
            from saleha.core.harness.test_runner import TestRunner
            qa_agent = QALeadAgent(model=self._resolve_model("qa"))
            suite = qa_agent.generate_test_suite(goal, current_code)
            if not suite.generated:
                with blackboard.lock:
                    blackboard.test_error = f"no tests generated: {suite.error}"
                return f"QA skipped: no tests generated ({suite.error})", {"passed": False, "ran": 0}
            # The old arm ran code + tests as a plain script, which only
            # defines `def test_...` functions: "tests passed" meant "the
            # module imported". The runner calls each test and counts them.
            run = TestRunner().run_suite(current_code, test_code=suite.test_code, timeout=15)
            err_msg = "" if run.passed else run.failure_report(300)
            with blackboard.lock:
                blackboard.test_code = suite.test_code
                blackboard.tests_ran = run.ran > 0
                blackboard.tests_passed = run.passed
                blackboard.test_count = run.ran
                blackboard.test_error = err_msg
            summary_msg = f"Ran {run.ran} model-written test(s): {'PASSED' if run.passed else f'FAILED ({err_msg})'}"
            return summary_msg, {
                "passed": run.passed,
                "test_count": run.ran,
                "error": err_msg,
                "verified_by": "model-written tests",
            }

        def _run_sre() -> Tuple[str, Dict[str, Any]]:
            sre_agent = ChaosResilienceAgent(model=self._resolve_model("sre"))
            chaos_res = sre_agent.run_chaos_test(goal)
            with blackboard.lock:
                blackboard.resilience_score = chaos_res.resilience_score_pct
                blackboard.circuit_breaker_patch = chaos_res.circuit_breaker_patch
            return (
                "Resilience not measured (no fault injection); circuit-breaker template attached",
                {"score": None, "measured": False},
            )

        parallel_phase3 = [
            ("arm_security", _run_security, (), {}),
            ("arm_qa", _run_qa, (), {}),
            ("arm_sre", _run_sre, (), {}),
        ]
        p3_res = self.worker_pool.execute_parallel(parallel_phase3, timeout_sec=self.timeout_sec)
        for task_id, role, name in [
            ("arm_security", ArmBrainRole.SECURITY, "SecurityBrain"),
            ("arm_qa", ArmBrainRole.QA, "QABrain"),
            ("arm_sre", ArmBrainRole.SRE, "SREBrain"),
        ]:
            tres = p3_res.get(task_id, WorkerTaskResult(success=False, error_message="Task dropped"))
            if not tres.success:
                out = ArmBrainOutput(
                    brain_role=role.value,
                    brain_name=name,
                    status="failed",
                    summary=tres.error_message or "Timeout",
                    duration_ms=tres.execution_time_ms,
                    error=tres.error_message,
                )
            else:
                summary, payload = tres.result
                out = ArmBrainOutput(
                    brain_role=role.value,
                    brain_name=name,
                    status="success",
                    summary=summary,
                    payload=payload,
                    duration_ms=tres.execution_time_ms,
                )
                self.bus.publish(
                    OctopusBrainCompletedEvent(
                        sender_agent=name,
                        brain_role=role.value,
                        status="success",
                        duration_ms=tres.execution_time_ms,
                        summary=summary,
                    )
                )
            blackboard.record_brain_output(out)
            if callback:
                callback(out)

        # =====================================================================
        # PHASE 4: CRITIQUE & CONSTITUTIONAL REVIEW (Arm 7)
        # =====================================================================
        def _run_critic() -> Tuple[str, Dict[str, Any]]:
            _require_code()
            rev_agent = ReviewerAgent(model=self._resolve_model("reviewer"))
            review = rev_agent.review_code(goal, blackboard.source_code)
            with blackboard.lock:
                blackboard.review_ran = True
                blackboard.review_approved = review.approved
                blackboard.review_feedback = review.feedback
            verdict = "APPROVED" if review.approved else "REVISION_REQUESTED"
            return f"Peer Review: {verdict}", {
                "approved": review.approved,
                "feedback": review.feedback,
            }

        _dispatch_and_record(ArmBrainRole.CRITIC, "CriticBrain", _run_critic)

        # =====================================================================
        # PHASE 5: CENTRAL MIND UNIFIED SYNTHESIS & CONFLICT RESOLUTION
        # =====================================================================
        if blackboard.conflicts:
            for conflict in blackboard.conflicts:
                self.bus.publish(
                    OctopusConflictResolvedEvent(
                        sender_agent="CentralMind",
                        conflict_type="security_code_reconciliation",
                        resolution=conflict,
                    )
                )

        # Success needs code, and every check to have run and come back
        # positive. With the old True defaults a crashed arm counted as a pass.
        overall_success = (
            blackboard.code_generated
            and blackboard.tests_ran and blackboard.tests_passed
            and blackboard.security_checked and blackboard.security_clean
            and blackboard.review_ran and blackboard.review_approved
        )

        total_dur_ms = round((time.perf_counter() - start_time) * 1000, 2)

        def _verdict(ran: bool, ok: bool, good: str, bad: str) -> str:
            return "NOT RUN" if not ran else (good if ok else bad)

        tests_line = _verdict(blackboard.tests_ran, blackboard.tests_passed, "PASSED",
                              f"FAILED ({blackboard.test_error})")
        if not blackboard.tests_ran and blackboard.test_error:
            tests_line = f"NOT RUN ({blackboard.test_error})"
        summary_lines = [
            f"Octopus Multi-Brain Run Completed in {total_dur_ms}ms",
            f"Mission: {goal}",
            f"Result: {'SUCCESS' if overall_success else 'FAILED'}",
            f"ADR: {blackboard.adr_title or 'none'}",
            f"Code: {'generated' if blackboard.code_generated else 'NOT GENERATED'}",
            f"Tests (model-written): {tests_line}",
            f"Security Audit: {_verdict(blackboard.security_checked, blackboard.security_clean, 'CLEAN', 'ISSUES_FOUND')}",
            "Resilience: not measured",
            f"Peer Review: {_verdict(blackboard.review_ran, blackboard.review_approved, 'APPROVED', 'REJECTED')}",
        ]
        summary_report = "\n".join(summary_lines)

        self.bus.publish(
            OctopusSynthesisCompletedEvent(
                sender_agent="CentralMind",
                success=overall_success,
                tests_passed=blackboard.tests_passed,
                security_clean=blackboard.security_clean,
            )
        )

        return OctopusExecutionResult(
            execution_id=exec_id,
            goal=goal,
            success=overall_success,
            final_code=blackboard.source_code,
            adr_title=blackboard.adr_title,
            security_clean=blackboard.security_clean,
            tests_passed=blackboard.tests_passed,
            resilience_score=blackboard.resilience_score,
            review_approved=blackboard.review_approved,
            total_duration_ms=total_dur_ms,
            brain_outputs=blackboard.brain_outputs,
            summary_report=summary_report,
            code_generated=blackboard.code_generated,
            tests_ran=blackboard.tests_ran,
            security_checked=blackboard.security_checked,
        )


# Global Singleton Instance
octopus_coordinator = OctopusCoordinator()
