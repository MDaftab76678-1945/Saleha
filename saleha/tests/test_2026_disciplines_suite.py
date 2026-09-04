"""
Unit & Integration Test Suite: 2026 5-Engineering Disciplines & Modular Architecture

Validates:
- Loop Engineering: MakerCheckerLoop, checkpointing, loop cycle detection
- Harness Engineering: PolyglotHarnessParser (pytest, cargo), approval gate, SWE-bench runner
- RAG Engineering: HybridRetriever (Reciprocal Rank Fusion)
- Graph Engineering: CallGraphNavigator multi-hop caller tracing
- Cognitive Engineering: DualProcessCognition (System 1 vs System 2)
- Verification & Quality: FormalSMTVerifier (AST SAT/UNSAT proofs), QualityGuard, TTCSolver
- Telemetry & Observability: SessionTracer, TokenAnalyticsEngine
- Swarm Orchestration: SwarmPipelineEngine, SwarmPBFTConsensus
- Platform & Runtime: SmartRouter, LSPEngine, SelfHealingEngine
"""

import unittest
import os
import tempfile
import time

from saleha.core.loop import (
    MakerCheckerLoop,
    LoopCheckpoint,
    tot_orchestrator,
    recursive_solver,
    deliberation_engine,
)
from saleha.core.harness import (
    PolyglotHarnessParser,
    ApprovalGate,
    approval_gate,
    SWEBenchRunner,
    SWEBenchTask,
    test_runner,
    code_executor,
)
from saleha.core.rag import (
    HybridRetriever,
    hybrid_retriever,
    semantic_search,
    vector_store,
    repo_context_packer,
)
from saleha.core.graph import (
    CallGraphNavigator,
    call_graph_navigator,
    codebase_indexer,
    dependency_graph,
)
from saleha.core.cognitive import (
    DualProcessCognition,
    dual_process_cognition,
    soul_engine,
    causal_world_model,
    persona_debate_engine,
    neuro_symbolic_engine,
)
from saleha.core.verification import (
    QualityGuard,
    quality_guard,
    TTCSolver,
    ttc_solver,
    FormalSMTVerifier,
    formal_smt_verifier,
    safety_guard,
    security_scanner,
    apex_97_validator,
)
from saleha.core.telemetry import (
    session_tracer,
    token_analytics,
    audit_log,
    metrics_tracker,
)
from saleha.core.swarm import (
    swarm_engine,
    message_bus,
    swarm_consensus,
    team_orchestrator,
    worker_pool,
    checkpoint_store,
)
from saleha.core.platform import (
    smart_router,
    model_provider,
    git_native,
    lsp_engine,
    mcp_hub,
    self_healer,
)


class Test2026EngineeringDisciplines(unittest.TestCase):
    """Test suite covering the 2026 5-discipline architectural transformation."""

    # ------------------------------------------------------------------
    # 1. Loop Engineering
    # ------------------------------------------------------------------
    def test_loop_engineering_checkpoint_and_cycle_detection(self):
        loop = MakerCheckerLoop(agent=None, enable_checkpoints=True)
        cp1 = loop.save_checkpoint(step=1, action="read_file", args_str="main.py", observation="class App: pass")
        self.assertEqual(cp1.step_number, 1)
        self.assertEqual(len(loop.checkpoints), 1)

        # Test loop cycle detection
        self.assertFalse(loop._detect_loop_cycle("read_file:a.py"))
        self.assertFalse(loop._detect_loop_cycle("read_file:b.py"))
        self.assertFalse(loop._detect_loop_cycle("read_file:c.py"))
        # Repeat identical cycle
        self.assertFalse(loop._detect_loop_cycle("read_file:a.py"))
        self.assertFalse(loop._detect_loop_cycle("read_file:b.py"))
        self.assertTrue(loop._detect_loop_cycle("read_file:c.py"))

    # ------------------------------------------------------------------
    # 2. Harness Engineering
    # ------------------------------------------------------------------
    def test_harness_polyglot_parser_and_swebench_assertion(self):
        # Pytest parsing
        pytest_out = "======= 14 passed, 1 failed in 2.34s ======="
        outcome = PolyglotHarnessParser.parse_pytest(pytest_out)
        self.assertEqual(outcome.passed, 14)
        self.assertEqual(outcome.failed, 1)
        self.assertFalse(outcome.success)
        self.assertAlmostEqual(outcome.duration_sec, 2.34, places=2)

        # Cargo test parsing
        cargo_out = "test result: ok. 18 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out"
        cargo_outcome = PolyglotHarnessParser.parse_cargo_test(cargo_out)
        self.assertTrue(cargo_outcome.success)
        self.assertEqual(cargo_outcome.passed, 18)

        # SWE-bench assertion evaluation runs against the code the harness
        # was actually given (mock_generated_code stands in for a real
        # generation result in mock mode) -- not a hardcoded correct
        # implementation regardless of input, which is what this module used
        # to do for exactly this function name.
        runner = SWEBenchRunner(model="mock")
        generated = "def safe_divide(a, b):\n    return 0.0 if b == 0 else a / b\n"
        passing_task = SWEBenchTask(
            instance_id="pass_test",
            repo_name="test/repo",
            problem_statement="Test statement",
            test_assertion="assert safe_divide(10, 2) == 5.0",
            mock_generated_code=generated,
        )
        res_pass = runner.evaluate_task(passing_task)
        self.assertTrue(res_pass.resolved)

        failing_task = SWEBenchTask(
            instance_id="fail_test",
            repo_name="test/repo",
            problem_statement="Test statement",
            test_assertion="assert safe_divide(10, 2) == 999.0",
            mock_generated_code=generated,
        )
        res_fail = runner.evaluate_task(failing_task)
        self.assertFalse(res_fail.resolved)

        # And with no generated code at all, the same assertion must fail --
        # there is no longer a hardcoded fallback to make it pass anyway.
        unresolved_task = SWEBenchTask(
            instance_id="no_code_test",
            repo_name="test/repo",
            problem_statement="Test statement",
            test_assertion="assert safe_divide(10, 2) == 5.0",
        )
        self.assertFalse(runner.evaluate_task(unresolved_task).resolved)

    # ------------------------------------------------------------------
    # 3. RAG Engineering
    # ------------------------------------------------------------------
    def test_rag_hybrid_retriever_rrf(self):
        retriever = HybridRetriever(k_rrf=60)
        # Vector store document addition
        vector_store.add_document("doc_01", "def compute_sha256_hash(data): return hashlib.sha256(data).hexdigest()")
        hits = retriever.retrieve("compute sha256 hash", top_k=3)
        self.assertIsInstance(hits, list)
        if hits:
            self.assertGreater(hits[0].rrf_score, 0.0)

    # ------------------------------------------------------------------
    # 4. Graph Engineering
    # ------------------------------------------------------------------
    def test_graph_call_navigator_impact_radius(self):
        navigator = CallGraphNavigator()
        impact = navigator.trace_impact_radius("save")
        self.assertIn("symbol", impact)
        self.assertIn("impacted_files", impact)
        self.assertIn("direct_caller_count", impact)

    # ------------------------------------------------------------------
    # 5. Cognitive Engineering
    # ------------------------------------------------------------------
    def test_cognitive_dual_process_system1_and_system2(self):
        cognition = DualProcessCognition()
        # System 1: Low complexity heuristic
        s1 = cognition.reason("format text to lowercase", complexity=0.2)
        self.assertEqual(s1.system_tier, "System_1_Intuitive")
        self.assertGreaterEqual(s1.confidence, 0.8)

        # System 2: High complexity deliberation
        s2 = cognition.reason("Synthesize distributed consensus Raft election algorithm", complexity=0.85)
        self.assertEqual(s2.system_tier, "System_2_Deliberative")
        self.assertTrue(s2.causal_explanation)

    # ------------------------------------------------------------------
    # 6. Verification & Quality
    # ------------------------------------------------------------------
    def test_verification_formal_smt_ast_sat_and_unsat(self):
        # formal_smt_verifier now asks Z3 a real, narrow question (can a
        # guarded division by a variable actually be zero?) instead of
        # emitting fixed "SMT_Z3_CERTIFICATE_SAT" text regardless of input.
        verifier = FormalSMTVerifier()
        self.assertTrue(verifier.verify_function_contract("def f(): pass", "f").z3_available)

        # A function with no division has nothing to prove.
        no_div_code = "def add(x: int, y: int) -> int:\n    return x + y\n"
        result_no_div = verifier.verify_function_contract(no_div_code, "add")
        self.assertEqual(result_no_div.divisions_found, 0)

        # A division guarded by `assert y != 0` is genuinely provable safe.
        guarded_code = "def safe_div(x, y):\n    assert y != 0\n    return x / y\n"
        result_guarded = verifier.verify_function_contract(guarded_code, "safe_div")
        self.assertEqual(result_guarded.divisions_proven_safe, 1)
        self.assertEqual(result_guarded.checks[0].status, "proven_safe")

        # Literal division by zero is never provable safe.
        bad_div_code = "def divide(x: int) -> float:\n    return x / 0\n"
        result_bad = verifier.verify_function_contract(bad_div_code, "divide")
        self.assertEqual(result_bad.divisions_proven_safe, 0)
        self.assertEqual(result_bad.checks[0].status, "not_proven")

        # An unguarded division by a variable is not provable safe either --
        # the checker does not assume success in the absence of evidence.
        unguarded_code = "def divide2(x, y):\n    return x / y\n"
        result_unguarded = verifier.verify_function_contract(unguarded_code, "divide2")
        self.assertEqual(result_unguarded.checks[0].status, "not_proven")

    # ------------------------------------------------------------------
    # 7. Telemetry & Observability
    # ------------------------------------------------------------------
    def test_telemetry_span_and_token_analytics(self):
        with session_tracer.span("test_2026_op", attributes={"layer": "test"}) as s:
            s.add_event("event_in_span", {"detail": "ok"})
            self.assertEqual(s.name, "test_2026_op")

        # Token analytics
        rec = token_analytics.record_invocation(
            model="qwen2.5-coder:7b",
            prompt_tokens=100,
            completion_tokens=50,
            duration_sec=0.5,
        )
        self.assertEqual(rec.total_tokens, 150)
        self.assertGreaterEqual(rec.cost_saved_usd, 0.0)

    # ------------------------------------------------------------------
    # 8. Swarm Orchestration
    # ------------------------------------------------------------------
    def test_swarm_router_and_pbft_consensus(self):
        dag = swarm_engine.router.route_goal_to_dag("Build a web dashboard with UI and database")
        self.assertIn("Designer", dag)
        self.assertIn("DataEngineer", dag)

        proposal = swarm_consensus.propose("CoderAgent", "test_file.py", "def test(): pass")
        self.assertTrue(proposal.proposal_id)

    # ------------------------------------------------------------------
    # 9. Platform & Runtime
    # ------------------------------------------------------------------
    def test_platform_smart_router_and_lsp_engine(self):
        best_model = smart_router.select_model_for_task("code", complexity_score=0.7)
        self.assertTrue(best_model)

        diag = lsp_engine.check_code("def foo(x):\n    return x + 1\n", filename="test.py")
        self.assertIsInstance(diag, list)


if __name__ == "__main__":
    unittest.main()
