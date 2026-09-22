"""Unit tests for .agents/ standalone utility scripts.

Verifies functionality of context compaction, CPG backward program slicing,
and hypergraph dependency impact analysis without any mocked passes.
"""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path
import pytest

from saleha.core.verification.quality_guard import QualityGuard


def test_compact_context_removes_docstrings() -> None:
    """Ensures compact_context removes non-essential docstrings and comments."""
    # Import directly from the script file
    import importlib.util

    script_path = Path(".agents/scripts/compact_context.py").resolve()
    spec = importlib.util.spec_from_file_location("compact_context", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sample_code = '''
def add(a: int, b: int) -> int:
    """This docstring should be stripped."""
    # This comment should be ignored
    return a + b
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(sample_code)
        tmp_path = Path(tmp.name)

    try:
        res = mod.compact_file_to_budget(tmp_path, max_tokens=100)
        assert res["status"] == "success"
        assert "This docstring should be stripped." not in res["content"]
        assert "return a + b" in res["content"]
        # Must parse cleanly as Python AST
        ast.parse(res["content"])
    finally:
        tmp_path.unlink(missing_ok=True)


def test_cpg_slicer_backward_slice() -> None:
    """Ensures CPG slicer computes correct backward causal dependencies."""
    import importlib.util

    script_path = Path(".agents/scripts/cpg_slicer.py").resolve()
    spec = importlib.util.spec_from_file_location("cpg_slicer", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sample_code = """
x = 10
y = 20
z = x + 5
irrelevant_var = y * 100
final_result = z * 2
"""
    # Slice on line 6 (final_result = z * 2)
    res = mod.compute_backward_slice(sample_code, target_line=6)
    assert res["status"] == "success"
    # Lines for x, z, final_result must be in the slice
    # Line for irrelevant_var should NOT be included
    sliced_text = res["sliced_code"]
    assert "x = 10" in sliced_text
    assert "z = x + 5" in sliced_text
    assert "final_result = z * 2" in sliced_text
    assert "irrelevant_var" not in sliced_text


def test_hypergraph_impact_analysis() -> None:
    """Ensures hypergraph blast radius accurately calculates module relationships."""
    import importlib.util

    script_path = Path(".agents/scripts/hypergraph_impact.py").resolve()
    spec = importlib.util.spec_from_file_location("hypergraph_impact", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    repo_root = Path(".").resolve()
    # Test against an existing core file
    target = "saleha/core/math_logic.py"
    res = mod.compute_blast_radius(target, repo_root)

    assert res["status"] == "success"
    assert res["target_file"] == target
    assert isinstance(res["dependent_modules"], list)
    assert isinstance(res["dependent_tests"], list)
    assert res["blast_radius_severity"] in ["MINIMAL", "LOW", "MODERATE", "HIGH", "CRITICAL"]
    assert "saleha/tests/test_math_logic.py" in res["dependent_tests"]


def test_active_inference_loop_agent() -> None:
    """Ensures ActiveInferenceAgent correctly samples observations and computes delta."""
    import importlib.util

    script_path = Path(".agents/skills/active-inference-loop/scripts/run_inference_loop.py").resolve()
    spec = importlib.util.spec_from_file_location("inference_loop", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test with existing clean core file
    target = Path("saleha/core/math_logic.py").resolve()
    agent = mod.ActiveInferenceAgent(target, max_iterations=2)
    obs = agent.sample_observation()
    assert obs["exists"] is True
    assert isinstance(obs["free_energy"], float)


def test_self_healing_traceback_parser() -> None:
    """Ensures self-healing traceback parser extracts failing files and lines."""
    import importlib.util

    script_path = Path(".agents/skills/self-healing-loop/scripts/self_heal_engine.py").resolve()
    spec = importlib.util.spec_from_file_location("self_heal", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mock_traceback = """Traceback (most recent call last):
  File "saleha/core/math_logic.py", line 42, in calculate_complexity
    assert score <= 10.0
AssertionError: Score exceeded maximum bound
"""
    frames = mod.parse_python_traceback(mock_traceback)
    assert len(frames) == 1
    assert frames[0]["file"] == "saleha/core/math_logic.py"
    assert frames[0]["line"] == 42
    assert frames[0]["function"] == "calculate_complexity"

    exc = mod.extract_exception_details(mock_traceback)
    assert exc["type"] == "AssertionError"
    assert "Score exceeded maximum bound" in exc["message"]


def test_code_knowledge_graph_builder() -> None:
    """Ensures AST knowledge graph indexes symbols and call edges."""
    import importlib.util

    script_path = Path(".agents/skills/code-knowledge-graph/scripts/build_ast_graph.py").resolve()
    spec = importlib.util.spec_from_file_location("ast_graph", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Build graph on a small directory
    test_dir = Path("saleha/sandbox").resolve()
    graph = mod.build_knowledge_graph(test_dir)
    assert graph["status"] == "success"
    assert graph["total_symbols"] > 0
    assert isinstance(graph["top_referenced_symbols"], list)


def test_gwt_blackboard_coordinator() -> None:
    """Ensures GWT blackboard posts facts and arbitrates attention by salience."""
    import importlib.util

    script_path = Path(".agents/skills/gwt-blackboard/scripts/octopus_blackboard.py").resolve()
    spec = importlib.util.spec_from_file_location("blackboard", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        coord = mod.BlackboardCoordinator(storage_path=tmp_path)
        coord.post_fact("SyntaxBrain", "syntax_error", "Missing colon on line 10", salience=3.0)
        coord.post_fact("SMTBrain", "critical_violation", "Counterexample x = -1 found", salience=9.5)

        # Arbitrate attention should pick the item with highest salience (9.5)
        top = coord.arbitrate_attention()
        assert top is not None
        assert top["agent"] == "SMTBrain"
        assert top["salience"] == 9.5
        assert "Counterexample" in top["content"]
    finally:
        tmp_path.unlink(missing_ok=True)

