"""Saleha Tests: Frontier Post-Training Alignment, PRM Compute Scaling & Self-Correction.

Verifies:
1. RLHVRVerifier: Physical hardware sandbox, Win32 Job Object bounds, and Z3 SMT contract proofs.
2. RLAIFAuditor: Constitutional AI rubrics and anti-vacuous-metric guarantees.
3. RLCDGenerator: Contrastive critique-revision pair synthesis with verified margin.
4. RLHFStore & DPOBatchExporter: Human developer preference store and HuggingFace TRL export.
5. ProcessRewardModel & PRMMCTSEngine: Step-level decomposition, early pruning, and PUCT search.
6. VerifiedSelfCorrectionEngine: Closed-loop repair in AgentPC with Lyapunov limit-cycle prevention.
"""

import json
from pathlib import Path
import pytest

from saleha.core.alignment.verifiable_rewards import (
    RewardSignal,
    RLHVRVerifier,
    RLAIFAuditor,
)
from saleha.core.alignment.contrastive_rlcd import (
    RLCDPair,
    RLCDGenerator,
)
from saleha.core.alignment.preference_store import (
    HumanFeedback,
    RLHFStore,
    DPOBatchExporter,
)
from saleha.core.prm_mcts_engine import (
    CodeStep,
    ProcessRewardModel,
    PRMNode,
    PRMMCTSEngine,
    PRMMCTSResult,
)
from saleha.core.self_correction import (
    VerifiedSelfCorrectionEngine,
    CorrectionResult,
)
from saleha.core.agent_pc import AgentPC


# ==============================================================================
# 1. RLHVR & RLAIF Verifier Tests
# ==============================================================================

def test_rlhvr_clean_code_passes() -> None:
    code = """
def divide_safe(a: int, b: int) -> float:
    \"\"\"Divides a by b safely with precondition check.\"\"\"
    assert b != 0, "Denominator cannot be zero"
    return a / b
"""
    test_code = """
assert divide_safe(10, 2) == 5.0
assert divide_safe(-6, 3) == -2.0
"""
    verifier = RLHVRVerifier(timeout_sec=5.0)
    sig: RewardSignal = verifier.verify_code(code, test_code=test_code)

    assert sig.ast_valid is True
    assert sig.passed_tests is True
    assert sig.security_clean is True
    assert sig.hardware_reward > 0.5
    assert sig.composite_score > 0.5
    assert sig.execution_time_ms >= 0.0


def test_rlhvr_failing_code_gives_negative_reward() -> None:
    code = """
def broken_calc(x: int) -> int:
    return x / 0  # Zero division hazard
"""
    test_code = "broken_calc(10)"
    verifier = RLHVRVerifier(timeout_sec=5.0)
    sig = verifier.verify_code(code, test_code=test_code)

    assert sig.ast_valid is True
    assert sig.passed_tests is False
    assert sig.hardware_reward < 0.0
    assert sig.composite_score < 0.0


def test_rlhvr_syntax_error_immediate_rejection() -> None:
    code = "def invalid_syntax(x :::: "
    verifier = RLHVRVerifier(timeout_sec=2.0)
    sig = verifier.verify_code(code)

    assert sig.ast_valid is False
    assert sig.passed_tests is False
    assert sig.hardware_reward == -1.0
    assert "syntax_error" in sig.details


def test_rlaif_constitutional_rubric_and_vacuous_defense() -> None:
    auditor = RLAIFAuditor()

    # Empty code should not vacuously claim 100% type coverage
    empty_rubric = auditor.audit_code("")
    assert empty_rubric["type_coverage"] == 0.0

    # Well-typed and defensive code
    good_code = """
def process_data(items: list[int], scale: float = 1.0) -> list[float]:
    assert len(items) > 0, "Items list must not be empty"
    try:
        return [float(x) * scale for x in items]
    except Exception:
        return []
"""
    rubric = auditor.audit_code(good_code)
    assert rubric["security_score"] == 1.0
    assert rubric["type_coverage"] == 1.0
    assert rubric["defensive_score"] >= 0.75
    assert rubric["composite_score"] > 0.7


# ==============================================================================
# 2. RLCD (Reinforcement Learning from Contrastive Dialogue)
# ==============================================================================

def test_rlcd_perturbation_and_margin_verification() -> None:
    clean_code = """
def compute_ratio(numerator: float, denominator: float) -> float:
    \"\"\"Calculates safe ratio.\"\"\"
    assert denominator != 0.0, "Denominator cannot be zero"
    return numerator / denominator
"""
    test_code = """
assert compute_ratio(10.0, 2.0) == 5.0
"""
    generator = RLCDGenerator(min_margin=0.10)
    pairs = generator.generate_contrastive_perturbations(
        clean_code=clean_code,
        prompt="Write a safe ratio calculation function in Python",
        test_code=test_code,
    )

    assert len(pairs) >= 1
    for pair in pairs:
        assert pair.chosen == clean_code
        assert pair.chosen != pair.rejected
        assert pair.margin_score >= 0.10
        assert pair.verified is True
        # Verify DPO translation
        dpo_pair = pair.to_dpo()
        assert dpo_pair.chosen == clean_code
        assert dpo_pair.rejected == pair.rejected
        assert dpo_pair.margin_score == pair.margin_score


# ==============================================================================
# 3. RLHF Preference Store & DPO Batch Exporter
# ==============================================================================

def test_rlhf_store_and_dpo_export(tmp_path: Path) -> None:
    db_file = tmp_path / "test_preferences.db"
    store = RLHFStore(db_path=db_file)

    # 1. Record human ratings
    fb1 = store.record_feedback(
        task_id="task_001",
        prompt="Write quicksort",
        candidate_code="def qs(arr): ...",
        rating=1.0,
        feedback_text="Clean and idiomatic",
    )
    fb2 = store.record_feedback(
        task_id="task_002",
        prompt="Write unsafe eval",
        candidate_code="eval(input())",
        rating=-1.0,
        feedback_text="Security hazard",
    )

    summary = store.get_summary()
    assert summary["total_feedback_entries"] == 2
    assert summary["positive_feedback_count"] == 1
    assert summary["negative_feedback_count"] == 1

    # 2. Record contrastive pair
    pair = store.record_pair(
        prompt="Safe division",
        chosen="def div(a: int, b: int) -> float:\n    assert b != 0\n    return a / b",
        rejected="def div(a, b):\n    return a / b",
        margin_score=0.35,
        source="rlcd_test",
    )
    assert pair.pair_id.startswith("pair_")

    pairs_list = store.list_pairs(min_margin=0.2)
    assert len(pairs_list) == 1
    assert pairs_list[0].margin_score == 0.35

    # 3. Export to JSONL
    export_file = tmp_path / "dpo_dataset.jsonl"
    exporter = DPOBatchExporter(store=store)
    exported_count = exporter.export_to_jsonl(export_file, min_margin=0.1)

    assert exported_count == 1
    assert export_file.exists()

    with open(export_file, "r", encoding="utf-8") as f:
        line = f.readline()
        record = json.loads(line)
        assert record["prompt"] == "Safe division"
        assert "chosen" in record
        assert "rejected" in record
        assert record["margin_score"] == 0.35


# ==============================================================================
# 4. PRM (Process Reward Model) & MCTS Engine
# ==============================================================================

def test_prm_step_decomposition_and_scoring() -> None:
    prm = ProcessRewardModel()

    code = """
from typing import List

def filter_positive_numbers(numbers: List[int]) -> List[int]:
    \"\"\"Filters positive integers from a list.\"\"\"
    assert numbers is not None, "List must not be None"
    result = []
    for x in numbers:
        if x > 0:
            result.append(x)
    return result
"""
    steps = prm.decompose_code_to_steps(code)
    assert len(steps) >= 3

    # Check step sequence
    step_types = [s.step_type for s in steps]
    assert "signature" in step_types
    assert "postconditions" in step_types

    for s in steps:
        assert s.is_valid is True
        assert 0.0 <= s.prm_score <= 1.0


def test_prm_early_pruning_on_security_violation() -> None:
    prm = ProcessRewardModel(prune_threshold=0.30)

    unsafe_code = """
import os
def delete_everything(path: str) -> None:
    os.system("rmdir /s /q " + path)
"""
    step = prm.evaluate_step(
        step_index=1,
        step_type="core_logic",
        code_fragment=unsafe_code,
        cumulative_code=unsafe_code,
    )

    assert step.is_valid is False
    assert step.prm_score < 0.30
    assert len(step.diagnostics) > 0


def test_prm_mcts_tree_search() -> None:
    engine = PRMMCTSEngine(c_puct=1.414, max_depth=3)

    c_good = """
def multiply(a: int, b: int) -> int:
    \"\"\"Multiplies two numbers.\"\"\"
    return a * b
"""
    c_bad = """
def multiply(a: int, b: int) -> int:
    raise RuntimeError("Intentional error")
"""
    test_code = "assert multiply(3, 4) == 12"

    result: PRMMCTSResult = engine.search(
        task_prompt="Implement integer multiplication",
        candidate_variations=[c_good, c_bad],
        test_code=test_code,
        max_iterations=5,
    )

    assert result.passed_tests is True
    assert "multiply" in result.best_code
    assert result.best_composite_score > 0.0
    assert result.total_nodes_created > 0
    assert len(result.step_trace) > 0
    # Five iterations over two distinct leaf programs: each is sandboxed once.
    assert result.details["sandbox_runs"] == 2


@pytest.mark.parametrize(
    "exit_stmt",
    ["import sys\nsys.exit(0)", "import os\nos._exit(0)", "raise SystemExit(0)"],
)
def test_rlhvr_early_exit_is_not_a_pass(exit_stmt: str) -> None:
    code = f"def f() -> int:\n    return 1\n{exit_stmt}\n"
    sig = RLHVRVerifier().verify_code(code, test_code="assert f() == 2")

    assert sig.passed_tests is False
    assert sig.details["run_completed"] is False
    assert sig.hardware_reward < 0.0


def test_rlhvr_marker_is_stripped_from_reported_output() -> None:
    sig = RLHVRVerifier().verify_code("print('hello')", test_code="assert True")

    assert sig.passed_tests is True
    assert sig.details["run_completed"] is True
    assert sig.details["sandbox_output"] == "hello"


def test_rlhvr_runs_in_scratch_dir_not_caller_cwd(tmp_path: Path) -> None:
    sig = RLHVRVerifier().verify_code("import os\nprint(os.getcwd())")
    assert Path(sig.details["sandbox_output"]).resolve() != Path.cwd().resolve()

    sig_pinned = RLHVRVerifier().verify_code("import os\nprint(os.getcwd())", cwd=str(tmp_path))
    assert Path(sig_pinned.details["sandbox_output"]).resolve() == tmp_path.resolve()


def test_prm_mcts_rejects_candidate_that_exits_before_tests() -> None:
    hacked = "def multiply(a: int, b: int) -> int:\n    return a + b\nraise SystemExit(0)\n"
    result = PRMMCTSEngine().search(
        task_prompt="multiply",
        candidate_variations=[hacked],
        test_code="assert multiply(3, 4) == 12",
        max_iterations=2,
    )

    assert result.passed_tests is False
    assert result.best_composite_score < 0.0


# ==============================================================================
# 5. Verified Self-Correction & Lyapunov Stability
# ==============================================================================

def test_self_correction_heals_zero_division(tmp_path: Path) -> None:
    pc = AgentPC(agent_role="test_corrector", base_dir=tmp_path / "pc_workspace")
    corrector = VerifiedSelfCorrectionEngine(pc=pc, max_iterations=3)

    failing_code = """
def compute_average(total: int, count: int) -> float:
    return total / count
"""
    test_code = """
assert compute_average(10, 2) == 5.0
assert compute_average(0, 0) == 0  # Fails with ZeroDivisionError on original code
"""

    result: CorrectionResult = corrector.correct_code(
        failing_code=failing_code,
        test_code=test_code,
        task_description="Fix division by zero when count is zero",
    )

    assert result.success is True
    assert result.final_reward is not None
    assert result.final_reward.passed_tests is True
    assert result.iterations_count == 1
    assert "compute_average" in result.repaired_code
    # The fix changes semantics (x / 0 -> 0); the result must say so.
    assert result.details["strategies_applied"] == ["zero_division_returns_0"]


def test_self_correction_lyapunov_limit_cycle_detection(tmp_path: Path) -> None:
    pc = AgentPC(agent_role="test_lyapunov", base_dir=tmp_path / "lyapunov_workspace")
    corrector = VerifiedSelfCorrectionEngine(pc=pc, max_iterations=4)

    # Code that cannot be fixed by naive division patching, causing repeated errors
    unfixable_code = """
def impossible_contract():
    raise AssertionError("Unsatisfiable synthetic constraint")
"""
    test_code = """
impossible_contract()
assert False, "Synthetic unsolvable constraint in test runner"
"""

    result: CorrectionResult = corrector.correct_code(
        failing_code=unfixable_code,
        test_code=test_code,
    )

    # No canned transform applies and no external generator: abort at once
    # instead of re-verifying unchanged code for every remaining iteration.
    assert result.success is False
    assert result.lyapunov_status == "ATTRACTOR_TRAPPED_ABORTED"
    assert result.iterations_count == 0
    assert "No untried repair candidate" in result.details["abort_reason"]
    assert len(result.error_history) == 1


def test_self_correction_does_not_mask_crash_as_repair(tmp_path: Path) -> None:
    pc = AgentPC(agent_role="test_mask", base_dir=tmp_path / "mask")
    corrector = VerifiedSelfCorrectionEngine(pc=pc, max_iterations=4)
    code = "def load(path):\n    return open(path).read().upper()\n"

    result = corrector.correct_code(code, test_code="load('/definitely/missing.txt')")

    assert result.success is False
    assert result.lyapunov_status == "ATTRACTOR_TRAPPED_ABORTED"
    assert "except Exception" not in result.repaired_code


def test_self_correction_runs_in_agent_pc_workspace(tmp_path: Path) -> None:
    pc = AgentPC(agent_role="test_cwd", base_dir=tmp_path / "cwd_pc")
    corrector = VerifiedSelfCorrectionEngine(pc=pc)

    result = corrector.correct_code(
        "import os\ndef f():\n    return 1 / 0\n",
        test_code="print(os.getcwd())\nf()",
    )

    assert result.success is True
    assert result.final_reward is not None
    reported_cwd = result.final_reward.details["sandbox_output"].splitlines()[0]
    assert Path(reported_cwd).resolve() == pc.workspace.root_path.resolve()


def test_self_correction_uses_external_patch(tmp_path: Path) -> None:
    pc = AgentPC(agent_role="test_ext", base_dir=tmp_path / "ext")
    corrector = VerifiedSelfCorrectionEngine(pc=pc, max_iterations=4)
    calls = []

    def patcher(code: str, prompt: str, tests: str) -> str:
        calls.append(code)
        return "def add(a, b):\n    return a + b\n"

    result = corrector.correct_code(
        "def add(a, b):\n    return a - b\n",
        test_code="assert add(2, 2) == 4",
        external_patch_fn=patcher,
    )

    assert result.success is True
    assert result.details["strategies_applied"] == ["external_patch"]
    assert len(calls) == 1


def test_self_correction_reports_external_patch_failure(tmp_path: Path) -> None:
    pc = AgentPC(agent_role="test_ext_err", base_dir=tmp_path / "ext_err")
    corrector = VerifiedSelfCorrectionEngine(pc=pc)

    def broken_patcher(code: str, prompt: str, tests: str) -> str:
        raise ConnectionError("model offline")

    result = corrector.correct_code(
        "def add(a, b):\n    return a - b\n",
        test_code="assert add(2, 2) == 4",
        external_patch_fn=broken_patcher,
    )

    assert result.success is False
    assert "ConnectionError: model offline" in result.details["abort_reason"]
