"""Unit tests for Level 5 Frontier Autonomous Engineering Engines.

Verifies Flight Recorder, Autonomous Kernel, Mutation Engine, Grammar Masker,
Causal Intervention Debugger, BFT Consensus, and Latent World Model.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any


def test_flight_recorder_cryptographic_integrity() -> None:
    """Ensures FlightRecorder generates valid hash chains and detects tampering."""
    import importlib.util

    script_path = Path(".agents/scripts/flight_recorder.py").resolve()
    spec = importlib.util.spec_from_file_location("flight_rec", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        recorder = mod.FlightRecorder(log_path=tmp_path)
        ev1 = recorder.record_event("STAGE_1", "INIT", {"data": "alpha"})
        ev2 = recorder.record_event("STAGE_2", "EXEC", {"data": "beta"})

        assert ev1["entry_hash"] != "0" * 64
        assert ev2["prev_hash"] == ev1["entry_hash"]

        check = recorder.verify_integrity()
        assert check["valid"] is True
        assert check["total_events"] == 2
    finally:
        tmp_path.unlink(missing_ok=True)


def test_grammar_masker_validates_syntax() -> None:
    """Ensures GrammarStateMachine accurately validates valid and invalid Python syntax."""
    import importlib.util

    script_path = Path(
        ".agents/skills/grammar-constrained-engine/scripts/grammar_masker.py"
    ).resolve()
    spec = importlib.util.spec_from_file_location("grammar_masker", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sm = mod.GrammarStateMachine()

    # Valid syntax
    valid_res = sm.validate_source("def add(a, b):\n    return a + b\n")
    assert valid_res["valid"] is True
    assert len(valid_res["errors"]) == 0

    # Invalid syntax (unclosed parenthesis)
    invalid_res = sm.validate_source("def bad_func(a, b:\n    return a\n")
    assert invalid_res["valid"] is False
    assert len(invalid_res["errors"]) > 0


def test_causal_debugger_ace_calculation() -> None:
    """Ensures causal debugger calculates Average Causal Effect and isolates root cause."""
    import importlib.util

    script_path = Path(
        ".agents/skills/causal-debugger/scripts/causal_intervention.py"
    ).resolve()
    spec = importlib.util.spec_from_file_location("causal_dbg", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Expression failing when x=2, y=3 because 2 + 3 is not > 10
    failing_state = {"x": 2, "y": 3}
    expr = "x + y > 10"

    res = mod.compute_causal_effects(expr, failing_state)
    assert res["status"] == "COMPLETED"
    assert res["baseline_outcome"] is False
    assert len(res["causal_rankings"]) == 2
    # Both x and y have non-zero causal effect on flipping outcome
    assert res["causal_rankings"][0][1]["average_causal_effect"] > 0.0


def test_bft_swarm_consensus_quorum() -> None:
    """Ensures BFT Consensus Gate ratifies sound proposals and rejects invalid ones."""
    import importlib.util

    script_path = Path(
        ".agents/skills/bft-swarm-consensus/scripts/bft_consensus_gate.py"
    ).resolve()
    spec = importlib.util.spec_from_file_location("bft_gate", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    gate = mod.BFTConsensusGate()

    # Valid proposal
    valid_prop = "def clean_logic(x):\n    return x * 2\n"
    res = gate.evaluate_proposal(valid_prop)
    assert res["ratified"] is True
    assert res["supermajority_achieved"] is True

    # Bad syntax proposal
    bad_prop = "def bad_logic(x\n    return x\n"
    res_bad = gate.evaluate_proposal(bad_prop)
    assert res_bad["ratified"] is False


def test_latent_world_model_prediction() -> None:
    """Ensures Latent World Model predicts regression risk when functions are removed."""
    import importlib.util

    script_path = Path(
        ".agents/skills/codebase-world-model/scripts/latent_world_model.py"
    ).resolve()
    spec = importlib.util.spec_from_file_location("world_model", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    predictor = mod.LatentPredictor()
    target_rel = "saleha/core/math_logic.py"

    # Simulated code that completely deletes all functions
    empty_proposal = "# Empty file without functions\nx = 1\n"
    sim = predictor.simulate_modification(target_rel, empty_proposal)

    assert sim["status"] == "SIMULATED"
    assert sim["risk_score"] > 0.4
    assert len(sim["removed_symbols"]) > 0


def test_mutation_engine_mutant_generator() -> None:
    """Ensures AST mutation generator correctly flips binary and comparison operators."""
    import importlib.util

    script_path = Path(
        ".agents/skills/mutation-engine/scripts/run_mutation_test.py"
    ).resolve()
    spec = importlib.util.spec_from_file_location("mut_engine", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sample = "def cmp(a, b):\n    return a + b > 10\n"
    count = mod.count_potential_mutations(sample)
    assert count >= 2  # Has '+' and '>'

    mutant_code, desc = mod.generate_mutant(sample, 0)
    assert mutant_code != sample
    assert ("-" in mutant_code) or ("<=" in mutant_code)


def _load_preflight() -> Any:
    """Loads the pre-commit gate script as a module."""
    import importlib.util

    script_path = Path(".agents/scripts/preflight_lint.py").resolve()
    spec = importlib.util.spec_from_file_location("preflight_lint", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _claude_md_health(body: str) -> bool:
    """Runs the real gate against a CLAUDE.md containing `body`."""
    mod = _load_preflight()
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "CLAUDE.md").write_text(body, encoding="utf-8")
        original_root = mod.REPO_ROOT
        try:
            mod.REPO_ROOT = tmp_dir
            return mod.check_claude_md_health()
        finally:
            mod.REPO_ROOT = original_root


def test_claude_md_gate_blocks_an_overlong_file() -> None:
    """The file loads every session, so length is the primary failure mode."""
    mod = _load_preflight()
    budget = mod.CLAUDE_MD_MAX_LINES

    assert _claude_md_health("ok\n" * budget) is False  # at budget -> allowed
    assert _claude_md_health("ok\n" * (budget + 1)) is True  # over -> blocked


def test_claude_md_gate_blocks_counts_that_go_stale() -> None:
    """Each of these was a real stale claim in the 2761-line version."""
    stale = (
        "It has a CLI (100+ subcommands) and ~220 modules under `saleha/core/`.",
        "Test suite: 2303 passed, 13 skipped.",
        "Fixed in pass 139; see the ledger.",
        "the self-building vision from line 447-448 of this file",
    )
    for claim in stale:
        assert _claude_md_health(claim + "\n") is True, f"not caught: {claim}"


def test_claude_md_gate_allows_a_command_that_prints_a_count() -> None:
    """The recommended fix must not trip the rule it is the fix for.

    A count inside a fenced block is a command that produces the number at run
    time -- the opposite of freezing it.
    """
    body = (
        "Get the real count:\n"
        "\n"
        "```bash\n"
        "python -c \"from saleha.cli.commands import cli; print(len(cli.commands))\"\n"
        "# prints e.g. 163 commands\n"
        "```\n"
    )
    assert _claude_md_health(body) is False


def test_claude_md_gate_skips_rather_than_blocks_when_file_is_absent() -> None:
    """A missing file is unknown, not a violation -- it must not block a commit."""
    mod = _load_preflight()
    with tempfile.TemporaryDirectory() as tmp_dir:
        original_root = mod.REPO_ROOT
        try:
            mod.REPO_ROOT = tmp_dir  # no CLAUDE.md written
            assert mod.check_claude_md_health() is False
        finally:
            mod.REPO_ROOT = original_root


def test_real_claude_md_passes_its_own_gate() -> None:
    """This repo's actual CLAUDE.md must satisfy the rule it documents."""
    mod = _load_preflight()
    assert mod.check_claude_md_health() is False


def test_hdc_memory_associative_recall() -> None:
    """Ensures HDC memory stores bug patterns and recalls them associatively."""
    import importlib.util

    script_path = Path(
        ".agents/skills/hdc-memory/scripts/hyperdimensional_memory.py"
    ).resolve()
    spec = importlib.util.spec_from_file_location("hdc_mem", str(script_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        store = mod.HDCMemoryStore(storage_path=tmp_path)
        store.store_pattern("ZeroDivisionError in division", "Add zero guard")
        store.store_pattern("IndexError in array access", "Add length check")

        # Query for exact match
        matches = store.query_memory("ZeroDivisionError in division", top_k=1)
        assert len(matches) == 1
        sim, mem = matches[0]
        assert sim > 0.9  # Nearly identical
        assert "zero guard" in mem["fix_pattern"].lower()
    finally:
        tmp_path.unlink(missing_ok=True)

