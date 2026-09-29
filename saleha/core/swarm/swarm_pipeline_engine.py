"""
Saleha Core: Autonomous Swarm Pipeline Engine & Dynamic DAG Router

Analyzes user task goals, dynamically constructs Directed Acyclic Graph (DAG) execution stages,
persists checkpoints to disk for zero-waste session resumption, and broadcasts events to AgentMessageBus.
"""

from __future__ import annotations

import contextlib
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from saleha.core.agent_contracts import (
    ArchitectOutputContract,
    CoderOutputContract,
    FinOpsOutputContract,
    QAOutputContract,
    ReviewerOutputContract,
    SecurityOutputContract,
)
from saleha.core.memory.semantic_memory_cache import semantic_memory
from saleha.core.merkle_provenance import merkle_provenance_ledger
from saleha.core.swarm.agent_message_bus import (
    ADRGeneratedEvent,
    CodeSynthesizedEvent,
    ReviewFeedbackEvent,
    SecurityVulnerabilityEvent,
    TaskAssignedEvent,
    TestExecutionEvent,
    TokenCompressedEvent,
    message_bus,
)
from saleha.core.swarm.swarm_checkpoint_store import SwarmCheckpoint, checkpoint_store


@dataclass
class SwarmPipelineStage:
    stage_id: str
    agent_role: str
    status: str = "pending"  # "pending", "running", "success", "failed"
    duration_ms: float = 0.0
    output_summary: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmExecutionResult:
    execution_id: str
    goal: str
    success: bool
    stages: List[SwarmPipelineStage]
    final_code: str
    adr_title: str
    security_clean: bool
    tests_passed: bool
    token_savings_pct: float
    total_duration_ms: float
    memory_recalled_count: int
    resumed_from_checkpoint: bool = False
    # What actually happened, so "did not run" never reads as "passed":
    # success requires code_generated, tests_ran and security_checked.
    code_generated: bool = False
    tests_ran: bool = False
    security_checked: bool = False


class AutonomousSwarmRouter:
    """Intelligent Intent Classifier & DAG Pipeline Builder."""

    def route_goal_to_dag(self, goal: str) -> List[str]:
        """Maps user requirements into an optimal sequence of specialized agent roles."""
        goal_lower = goal.lower()

        # Base engineering pipeline
        stages = ["Architect", "Coder", "SecurityGuard", "QALead", "Reviewer", "FinOpsOptimizer"]

        if any(w in goal_lower for w in ["ui", "css", "design", "frontend", "landing", "style"]):
            stages.insert(1, "Designer")
            stages.insert(2, "WebDev")

        if any(w in goal_lower for w in ["database", "sql", "etl", "vector", "pipeline", "schema"]):
            stages.insert(1, "DataEngineer")

        if any(w in goal_lower for w in ["docker", "k8s", "kubernetes", "ci/cd", "deploy", "helm"]):
            stages.append("DevOps")

        if any(w in goal_lower for w in ["outage", "crash", "bug", "traceback", "rca", "incident"]):
            stages.insert(0, "SREIncident")

        if any(w in goal_lower for w in ["skill", "catalog", "synthesize skill"]):
            stages.append("NewSkillCreator")

        return stages


class SwarmPipelineEngine:
    """Executes Dynamic Multi-Agent DAG Pipelines with Checkpointing & Session Resumption."""

    GENERATOR_ATTEMPTS = 3

    def __init__(self, router: Optional[AutonomousSwarmRouter] = None, model: str = "auto",
                 candidates: int = 1):
        self.router = router or AutonomousSwarmRouter()
        self.model = model
        # >1 turns on cross-checking in the QA stage: that many solutions and
        # two test suites, winner chosen by agreement (see verification/cross_check).
        self.candidates = max(1, candidates)

    def _cross_check_stage(self, goal: str, first_code: str, first_suite: Any,
                           qa_agent: Any, stage: SwarmPipelineStage) -> bool:
        """
        Pick the solution by agreement instead of trusting one model-written
        suite (a 3B model wrote `assertFalse(is_palindrome("A"))` for a
        case-insensitive task). Returns False when there is not enough to
        cross-check (under 2 distinct solutions), so the caller falls back to
        the single-suite run.
        """
        from saleha.agents.coder import CoderAgent
        from saleha.agents.security_guard import SecurityGuardAgent
        from saleha.core.verification.cross_check import cross_check

        coder = CoderAgent(model=self._resolve_model("coder"))
        pool = [first_code]
        for _ in range(self.candidates - 1):
            extra = coder.generate_code(goal)
            if extra.success and extra.code.strip():
                pool.append(extra.code)
        suites = [first_suite.test_code]
        second = qa_agent.generate_test_suite(goal, first_code)
        if second.generated:
            suites.append(second.test_code)

        result = cross_check(pool, suites)
        if result.reason.startswith("needs"):
            return False

        # Agreement between independent solutions is the evidence; a lone
        # winner has none.
        agreed = result.winner_index is not None and len(result.group) >= 2
        code = result.winner_code if result.winner_index is not None else first_code
        payload: Dict[str, Any] = {
            "code": code,
            "agreed": agreed,
            "agreement": result.agreement,
            "candidates": result.candidates,
            "suites": len(suites),
            "verified_by": "agreement between model-written solutions and tests",
        }
        if code != first_code:
            # The security stage scanned the first solution, not this one.
            audit = SecurityGuardAgent(model=self._resolve_model("security")).audit_and_harden(goal, code)
            payload.update(rescanned=True, is_secure=audit.is_secure)
        stage.payload = payload
        if not agreed:
            stage.status = "failed"
        stage.output_summary = (
            f"Cross-checked {result.candidates} distinct solution(s) x {len(suites)} test suite(s): "
            f"{result.agreement}" + ("" if agreed else " -- no agreement, not verified")
        )
        return True

    def _oracle_check(self, goal: str, code: str) -> Optional[Dict[str, Any]]:
        """
        Evidence that does not come from the same model-written tests: ask for
        a brute-force version and an input generator, then compare outputs on
        random inputs (verification/oracle_check). None when the goal names no
        function (`name(`), so there is nothing to call.
        """
        from saleha.agents.coder import CoderAgent
        from saleha.core.verification.oracle_check import (
            GENERATOR_PROMPT,
            ORACLE_PROMPT,
            differential_check,
            entry_point,
        )
        entry = entry_point(goal)
        if entry is None:
            return None
        coder = CoderAgent(model=self._resolve_model("coder"))
        oracle = coder.generate_code(ORACLE_PROMPT.format(task=goal))
        if not (oracle.success and oracle.code.strip()):
            return {"ran": False, "supported": False, "mismatch": "",
                    "reason": "model gave no brute-force version"}
        # A 3B model's generator often crashes on part of its draws (real run:
        # 107/200), leaving too few inputs to vouch. A fresh generator is cheap
        # and changes nothing that was already decided.
        result: Dict[str, Any] = {"ran": False, "supported": False, "mismatch": "",
                                  "reason": "model gave no input generator"}
        for attempt in range(1, self.GENERATOR_ATTEMPTS + 1):
            gen = coder.generate_code(GENERATOR_PROMPT.format(task=goal, entry=entry))
            if not (gen.success and gen.code.strip()):
                continue
            v = differential_check(code, oracle.code, gen.code, entry)
            result = {"ran": True, "supported": v.supported, "checked": v.checked,
                      "mismatch": v.mismatch, "reason": v.reason, "generator_attempts": attempt}
            if v.supported or v.mismatch:
                break
        return result

    def _resolve_model(self, task_role: str) -> str:
        """Dynamically resolves model: uses test mock when in test mode or explicitly requested,
        otherwise routes to real local models via smart_router."""
        if os.environ.get("SALEHA_TEST_MODE") == "1" or self.model == "mock":
            return "mock"
        if self.model and self.model != "auto":
            return self.model
        try:
            from saleha.core.platform.smart_router import smart_router
            return smart_router.select_model_for_task(task_role)
        except Exception:
            return "auto"

    def execute_swarm(
        self,
        goal: str,
        execution_id: Optional[str] = None,
        callback: Optional[Callable[[SwarmPipelineStage], None]] = None
    ) -> SwarmExecutionResult:
        """Executes full multi-agent pipeline with real-time event broadcasting and checkpointing."""
        exec_id = execution_id or str(uuid.uuid4())[:8]
        start_time = time.time()

        # 1. Semantic Memory Retrieval (Recall prior relevant patterns)
        relevant_memories = semantic_memory.search_memory(goal, top_k=2)

        # 2. Build DAG
        role_sequence = self.router.route_goal_to_dag(goal)
        stages: List[SwarmPipelineStage] = []

        # Initialize Checkpoint
        cp = SwarmCheckpoint(
            execution_id=exec_id,
            goal=goal,
            role_sequence=role_sequence,
            status="in_progress"
        )
        checkpoint_store.save_checkpoint(cp)

        # Broadcast Task Assigned Event
        message_bus.publish(TaskAssignedEvent(
            sender_agent="SwarmRouter",
            task_goal=goal,
            assigned_to=",".join(role_sequence)
        ))

        # Pipeline state accumulators. Every verdict starts as "not done":
        # these used to start True, so a stage that never ran counted as
        # secure / passed.
        adr_title = f"ADR: {goal}"
        source_code = ""
        code_generated = False
        is_secure = False
        security_checked = False
        tests_passed = False
        tests_ran = False
        savings_pct = 0.0

        for idx, role in enumerate(role_sequence, start=1):
            stage_id = f"stage_{idx}_{role.lower()}"
            stage = SwarmPipelineStage(stage_id=stage_id, agent_role=role, status="running")
            stage_start = time.time()

            if callback:
                callback(stage)

            # Lazy load agents to avoid circular imports
            if role == "Architect":
                from saleha.agents.architect import ArchitectAgent
                agent = ArchitectAgent(model=self._resolve_model("architect"))
                design = agent.design_system(goal)
                adr_title = design.adr_title
                contract = ArchitectOutputContract(
                    adr_title=design.adr_title,
                    pattern=design.pattern,
                    components=design.components,
                    system_design_md=design.system_design_md,
                )
                contract.validate()
                stage.output_summary = f"Generated Hexagonal ADR ({design.pattern}) with {len(design.components)} components"
                stage.payload = {"adr": design.system_design_md, "pattern": design.pattern}
                message_bus.publish(ADRGeneratedEvent(
                    sender_agent="ArchitectAgent",
                    adr_title=design.adr_title,
                    pattern=design.pattern,
                    components=design.components
                ))

            elif role == "Coder":
                from saleha.agents.coder import CoderAgent
                agent = CoderAgent(model=self._resolve_model("coder"))
                resp = agent.generate_code(goal)
                if resp.success and resp.code.strip():
                    source_code = resp.code
                    code_generated = True
                    contract = CoderOutputContract(source_code=source_code)
                    contract.validate()
                    stage.output_summary = f"Generated code ({len(source_code)} chars)"
                    stage.payload = {"code": source_code}
                    message_bus.publish(CodeSynthesizedEvent(
                        sender_agent="CoderAgent",
                        source_code=source_code
                    ))
                else:
                    # This used to substitute `def execute(): return True`
                    # and carry on, so security, QA and review all ran
                    # against a placeholder and the swarm could report
                    # success with no model reachable.
                    stage.status = "failed"
                    stage.output_summary = f"No code generated: {resp.error or 'empty model output'}"
                    stage.payload = {"error": resp.error}

            elif role in ("SecurityGuard", "QALead", "Reviewer") and not code_generated:
                stage.status = "skipped"
                stage.output_summary = f"{role} skipped: no generated code to check"

            elif role == "SecurityGuard":
                from saleha.agents.security_guard import SecurityGuardAgent
                agent = SecurityGuardAgent(model=self._resolve_model("security"))
                audit = agent.audit_and_harden(goal, source_code)
                security_checked = True
                # is_secure is the verdict on the code as generated. The regex
                # auto-patch below is not re-audited, so it does not flip it.
                is_secure = audit.is_secure
                source_code = audit.hardened_code or source_code
                contract = SecurityOutputContract(
                    is_secure=is_secure,
                    vulnerabilities_found=audit.vulnerabilities_found,
                    hardened_code=source_code
                )
                contract.validate()
                if not is_secure:
                    stage.status = "failed"
                stage.output_summary = (
                    "Security scan: clean" if is_secure else
                    f"Security scan: {len(audit.vulnerabilities_found)} issue(s) found; "
                    f"auto-patch attempted, not re-verified"
                )
                stage.payload = {"is_secure": is_secure, "vulnerabilities": audit.vulnerabilities_found}
                message_bus.publish(SecurityVulnerabilityEvent(
                    sender_agent="SecurityGuardAgent",
                    is_secure=is_secure,
                    vulnerabilities=audit.vulnerabilities_found
                ))

            elif role == "QALead":
                from saleha.agents.qa_lead import QALeadAgent
                from saleha.core.harness.test_runner import TestRunner
                agent = QALeadAgent(model=self._resolve_model("qa"))
                suite = agent.generate_test_suite(goal, source_code)
                if not suite.generated:
                    stage.status = "skipped"
                    stage.output_summary = f"QA skipped: no tests generated ({suite.error})"
                    stage.payload = {"error": suite.error}
                elif self.candidates > 1 and self._cross_check_stage(goal, source_code, suite, agent, stage):
                    # Cross-check decided the stage; take its verdict and code.
                    source_code = stage.payload["code"]
                    tests_ran = True
                    tests_passed = stage.payload["agreed"]
                    if stage.payload.get("rescanned"):
                        is_secure = stage.payload["is_secure"]
                else:
                    # Run through the structured runner. The old stage ran
                    # code + tests as a plain script, which only *defines*
                    # `def test_...` functions -- "tests passed" meant "the
                    # module imported". The runner calls every test, counts
                    # them, and refuses a suite that ran none.
                    run = TestRunner().run_suite(source_code, test_code=suite.test_code, timeout=15)
                    tests_ran = run.ran > 0
                    tests_passed = run.passed
                    # The tests come from the same model as the code and share
                    # its blind spots; a concrete input where the code differs
                    # from a brute-force version overrides their pass.
                    oracle = self._oracle_check(goal, source_code) if tests_passed else None
                    if oracle and oracle["mismatch"]:
                        tests_passed = False
                    contract = QAOutputContract(
                        framework=suite.framework,
                        test_code=suite.test_code,
                        test_case_count=run.ran,
                        passed=tests_passed
                    )
                    contract.validate()
                    if not tests_passed:
                        stage.status = "failed"
                    if oracle and oracle["mismatch"]:
                        verdict_text = f"tests passed, but differs from a brute-force version: {oracle['mismatch']}"
                    elif tests_passed:
                        verdict_text = "PASSED" + (
                            f"; matches a brute-force version on {oracle['checked']} random inputs"
                            if oracle and oracle["supported"] else "")
                    else:
                        verdict_text = "FAILED (" + run.failure_report(200) + ")"
                    stage.output_summary = (
                        f"Ran {run.ran} model-written test(s) against the generated code: {verdict_text}"
                    )
                    stage.payload = {
                        "test_code": suite.test_code,
                        "test_count": run.ran,
                        "failures": [f.test_name for f in run.failures],
                        "error": run.error[:500],
                        # The tests come from a model too; this is not an
                        # independent check of the task.
                        "verified_by": "model-written tests",
                        "oracle": oracle,
                    }
                    message_bus.publish(TestExecutionEvent(
                        sender_agent="QALeadAgent",
                        passed=tests_passed,
                        tests_count=run.ran
                    ))

            elif role == "Reviewer":
                from saleha.agents.reviewer import ReviewerAgent
                agent = ReviewerAgent(model=self._resolve_model("reviewer"))
                rev = agent.review_code(goal, source_code)
                contract = ReviewerOutputContract(
                    approved=rev.approved,
                    score=9.5 if rev.approved else 5.0,
                    feedback=rev.feedback
                )
                contract.validate()
                stage.output_summary = f"Senior Code Review: {'APPROVED' if rev.approved else 'NEEDS_WORK'}"
                stage.payload = {"approved": rev.approved, "feedback": rev.feedback}
                message_bus.publish(ReviewFeedbackEvent(
                    sender_agent="ReviewerAgent",
                    approved=rev.approved,
                    feedback=rev.feedback
                ))

            elif role == "FinOpsOptimizer":
                from saleha.agents.finops_optimizer import FinOpsOptimizerAgent
                agent = FinOpsOptimizerAgent(model=self._resolve_model("finops"))
                res = agent.compress_and_optimize(source_code or goal)
                savings_pct = res.token_savings_pct
                contract = FinOpsOutputContract(
                    original_tokens=res.original_tokens_est,
                    optimized_tokens=res.optimized_tokens_est,
                    token_savings_pct=savings_pct,
                    annual_cost_savings_usd=res.projected_annual_usd
                )
                contract.validate()
                # Report the measured quantity (tokens saved on this call),
                # not a yearly dollar figure. The old summary read "Saved
                # ~$10.00/yr" off a hardcoded 1M-calls/yr assumption and shipped
                # it into GitHub PR bodies as if it were an observed saving.
                stage.output_summary = (
                    f"Context compressed by {savings_pct}% "
                    f"({res.saved_tokens_est} est. tokens saved this call)"
                )
                stage.payload = {
                    "savings_pct": savings_pct,
                    "saved_tokens_est": res.saved_tokens_est,
                    "savings_per_call_usd": res.savings_per_call_usd,
                    "projected_annual_usd": res.projected_annual_usd,
                    "projection_call_volume": res.projection_call_volume,
                }
                message_bus.publish(TokenCompressedEvent(
                    sender_agent="FinOpsOptimizerAgent",
                    original_tokens=res.original_tokens_est,
                    compressed_tokens=res.optimized_tokens_est,
                    savings_pct=savings_pct
                ))

            else:
                # No agent is wired for this role. It used to report
                # "completed stage execution" with status success.
                stage.status = "skipped"
                stage.output_summary = f"{role}: no agent implemented for this role; nothing ran"

            stage.duration_ms = round((time.time() - stage_start) * 1000, 2)
            if stage.status == "running":
                stage.status = "success"
            stages.append(stage)

            # Record this stage in the cryptographic Merkle provenance chain.
            # merkle_provenance_ledger's hashing and tamper-detection were
            # always real (verified by test_merkle_provenance.py), but
            # nothing in production ever called record_event() -- the
            # `saleha merkle-audit` CLI command could only ever report
            # "Ledger is empty and untampered.", which is honest but useless
            # as an audit trail. Recording is best-effort: a hashing failure
            # here must not break the pipeline it is meant to be observing.
            with contextlib.suppress(Exception):
                merkle_provenance_ledger.record_event(
                    action_type=stage.agent_role.lower(),
                    agent_id=f"{stage.agent_role}Agent",
                    data=stage.output_summary,
                )

            # Persist intermediate checkpoint
            cp.completed_stages.append({
                "stage_id": stage.stage_id,
                "role": stage.agent_role,
                "status": stage.status,
                "duration_ms": stage.duration_ms,
                "summary": stage.output_summary,
            })
            cp.state_payload = {
                "adr_title": adr_title,
                "source_code": source_code,
                "code_generated": code_generated,
                "is_secure": is_secure,
                "security_checked": security_checked,
                "tests_passed": tests_passed,
                "tests_ran": tests_ran,
                "savings_pct": savings_pct,
            }
            checkpoint_store.save_checkpoint(cp)

            if callback:
                callback(stage)

        # 3. Finalize Checkpoint and Store in Semantic Memory
        cp.status = "completed"
        checkpoint_store.save_checkpoint(cp)

        total_duration = round((time.time() - start_time) * 1000, 2)

        # Success needs every check to have actually run and come back
        # positive. It was once hardcoded True, then `is_secure and
        # tests_passed` with both flags starting True -- so a pipeline whose
        # checks never ran still succeeded.
        overall_success = _overall_success(code_generated, security_checked, is_secure,
                                           tests_ran, tests_passed)

        # Only a verified result becomes a reusable pattern; recalling a
        # failed or unchecked one would seed the next run with it.
        if overall_success:
            semantic_memory.store_memory(
                category="pattern",
                title=f"Swarm Pattern: {goal}",
                content=f"ADR: {adr_title}\nImplementation Details: {source_code[:200]}...",
                tags=[role.lower() for role in role_sequence]
            )

        return SwarmExecutionResult(
            execution_id=exec_id,
            goal=goal,
            success=overall_success,
            stages=stages,
            final_code=source_code,
            adr_title=adr_title,
            security_clean=is_secure,
            tests_passed=tests_passed,
            token_savings_pct=savings_pct,
            total_duration_ms=total_duration,
            memory_recalled_count=len(relevant_memories),
            resumed_from_checkpoint=False,
            code_generated=code_generated,
            tests_ran=tests_ran,
            security_checked=security_checked,
        )

    def resume_swarm(
        self,
        execution_id: str,
        callback: Optional[Callable[[SwarmPipelineStage], None]] = None
    ) -> SwarmExecutionResult:
        """
        Return a completed run from its checkpoint, or re-run an unfinished one.

        An unfinished run is re-executed from the first stage, not resumed
        mid-pipeline (the old docstring claimed "from the exact last saved
        stage"; the code never did that). A completed run's verdict is
        recomputed from the saved flags. It used to be `success=True` for any
        completed checkpoint, with missing flags defaulting to True.
        """
        cp = checkpoint_store.get_checkpoint(execution_id)
        if not cp:
            raise ValueError(f"No checkpoint found for execution ID '{execution_id}'")

        if cp.status == "completed":
            stages = [
                SwarmPipelineStage(
                    stage_id=s.get("stage_id", ""),
                    agent_role=s.get("role", ""),
                    # Checkpoints written before stage status was saved do
                    # not say how a stage ended; do not claim "success".
                    status=s.get("status", "unknown"),
                    duration_ms=s.get("duration_ms", 0.0),
                    output_summary=s.get("summary", ""),
                )
                for s in cp.completed_stages
            ]
            state = cp.state_payload or {}
            code_generated = bool(state.get("code_generated", False))
            security_checked = bool(state.get("security_checked", False))
            is_secure = bool(state.get("is_secure", False))
            tests_ran = bool(state.get("tests_ran", False))
            tests_passed = bool(state.get("tests_passed", False))
            return SwarmExecutionResult(
                execution_id=cp.execution_id,
                goal=cp.goal,
                success=_overall_success(code_generated, security_checked, is_secure,
                                         tests_ran, tests_passed),
                stages=stages,
                final_code=state.get("source_code", ""),
                adr_title=state.get("adr_title", ""),
                security_clean=security_checked and is_secure,
                tests_passed=tests_ran and tests_passed,
                token_savings_pct=state.get("savings_pct", 0.0),
                total_duration_ms=sum(s.duration_ms for s in stages),
                memory_recalled_count=0,
                resumed_from_checkpoint=True,
                code_generated=code_generated,
                tests_ran=tests_ran,
                security_checked=security_checked,
            )

        # Unfinished: run the whole pipeline again under the same id.
        return self.execute_swarm(goal=cp.goal, execution_id=cp.execution_id, callback=callback)


def _overall_success(code_generated: bool, security_checked: bool, is_secure: bool,
                     tests_ran: bool, tests_passed: bool) -> bool:
    """A run succeeds only if code exists and both checks ran and passed."""
    return code_generated and security_checked and is_secure and tests_ran and tests_passed


# Global Singleton Instance
swarm_engine = SwarmPipelineEngine()
