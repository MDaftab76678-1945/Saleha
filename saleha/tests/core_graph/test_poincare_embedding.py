"""Tests for learned Poincare embeddings and the co-change benchmark."""

import subprocess
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pytest

from saleha.core.graph import poincare_embedding as pe
from saleha.core.graph.cochange_bench import (
    CodeGraph,
    build_code_graph,
    evaluate_rankers,
    load_cochange_commits,
)


def _tree_edges(branching: int = 3, depth: int = 4) -> Tuple[List[Tuple[int, int]], int]:
    """Complete tree in heap order: node k's parent is (k - 1) // branching."""
    n = sum(branching**level for level in range(depth + 1))
    return [((k - 1) // branching, k) for k in range(1, n)], n


@pytest.mark.parametrize("geometry", pe.GEOMETRIES)
def test_gradients_match_finite_differences(geometry: str) -> None:
    fn = pe._poincare_dist_and_grads if geometry == "poincare" else pe._euclidean_dist_and_grads
    rng = np.random.default_rng(3)
    u, v = rng.uniform(-0.4, 0.4, 4), rng.uniform(-0.4, 0.4, 4)
    _, grad_u, grad_v = fn(u, v)
    h = 1e-6
    num_u = [(pe.distance(u + e, v, geometry) - pe.distance(u - e, v, geometry)) / (2 * h) for e in np.eye(4) * h]
    num_v = [(pe.distance(u, v + e, geometry) - pe.distance(u, v - e, geometry)) / (2 * h) for e in np.eye(4) * h]
    assert np.allclose(grad_u, num_u, atol=1e-7)
    assert np.allclose(grad_v, num_v, atol=1e-7)


def test_poincare_distance_known_values() -> None:
    origin, point = np.zeros(2), np.array([0.5, 0.0])
    assert pe.poincare_distance(origin, origin) == 0.0
    assert pe.poincare_distance(origin, point) == pytest.approx(2 * np.arctanh(0.5))
    assert pe.poincare_distance(point, origin) == pytest.approx(pe.poincare_distance(origin, point))


def test_reconstruction_map_scores_rankings() -> None:
    path = [(0, 1), (1, 2)]
    good = np.array([[0.0], [1.0], [2.0]])
    assert pe.reconstruction_map(good, "euclidean", path) == pytest.approx(1.0)
    # 0 and 2 placed together, 1 far away: ends rank their only neighbour second.
    bad = np.array([[0.0], [5.0], [0.1]])
    assert pe.reconstruction_map(bad, "euclidean", path) == pytest.approx(2 / 3)


def test_poincare_beats_euclidean_on_tree_at_dim_2() -> None:
    edges, n = _tree_edges()
    hyp = pe.train_embedding(edges, n, 2, "poincare", epochs=200, lr=0.1, seed=0)
    euc = pe.train_embedding(edges, n, 2, "euclidean", epochs=200, lr=0.3, seed=0)
    hyp_map = pe.reconstruction_map(hyp.coords, "poincare", edges)
    euc_map = pe.reconstruction_map(euc.coords, "euclidean", edges)
    assert np.all(np.linalg.norm(hyp.coords, axis=1) < 1.0)
    assert hyp_map > euc_map + 0.1


def test_training_refuses_nothing_to_learn() -> None:
    with pytest.raises(ValueError):
        pe.train_embedding([], 5, 2)
    with pytest.raises(ValueError):
        pe.train_embedding([(1, 1)], 5, 2)  # self-loop only
    with pytest.raises(ValueError):
        pe.train_embedding([(0, 1)], 5, 2, geometry="spherical")
    with pytest.raises(ValueError):
        pe.reconstruction_map(np.zeros((3, 2)), "poincare", [])


def test_build_code_graph_resolves_imports_and_lists_skips(tmp_path: Path) -> None:
    pkg = tmp_path / "saleha"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("from saleha import b\nimport json\n", encoding="utf-8")
    (pkg / "b.py").write_text("x = 1\n", encoding="utf-8")
    (pkg / "sub" / "c.py").write_text("from ..a import thing\n", encoding="utf-8")
    (pkg / "broken.py").write_text("def (:\n", encoding="utf-8")

    graph = build_code_graph(tmp_path)
    idx = graph.index
    undirected = {tuple(sorted(e)) for e in graph.edges}
    assert tuple(sorted((idx["saleha/a.py"], idx["saleha/b.py"]))) in undirected
    assert tuple(sorted((idx["saleha/sub/c.py"], idx["saleha/a.py"]))) in undirected
    assert tuple(sorted((idx["saleha/sub"], idx["saleha/sub/c.py"]))) in undirected
    assert graph.import_edges == 2
    assert [path for path, _ in graph.skipped] == ["saleha/broken.py"]
    assert "saleha/broken.py" in graph.files


def _git(repo: Path, *args: str) -> None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr


def test_load_cochange_commits_filters_by_size(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / name).write_text("0\n", encoding="utf-8")
    _git(tmp_path, "add", "a.py", "b.py")
    _git(tmp_path, "commit", "-q", "--no-verify", "-m", "two files")
    (tmp_path / "a.py").write_text("1\n", encoding="utf-8")
    _git(tmp_path, "commit", "-q", "--no-verify", "-am", "one file")
    for name in ("a.py", "b.py", "c.py"):
        (tmp_path / name).write_text("2\n", encoding="utf-8")
    _git(tmp_path, "add", "c.py")
    _git(tmp_path, "commit", "-q", "--no-verify", "-am", "three files")

    history = load_cochange_commits(tmp_path, {"a.py", "b.py", "c.py"}, max_files=2)
    assert history.total == 3
    assert history.commits == [["a.py", "b.py"]]
    assert (history.too_few, history.too_many) == (1, 1)


def test_load_cochange_commits_reports_git_failure(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        load_cochange_commits(tmp_path / "not-a-repo", {"a.py"})


def _toy_graph() -> CodeGraph:
    files = ["f0", "f1", "f2", "f3"]
    return CodeGraph(files, {f: i for i, f in enumerate(files)}, [], files)


def test_evaluate_rankers_measures_recall() -> None:
    graph = _toy_graph()
    partner = {0: 1, 1: 0}

    def oracle(seed: int) -> np.ndarray:
        scores = np.ones(4)
        scores[partner[seed]] = 0.0
        return scores

    def anti(seed: int) -> np.ndarray:
        scores = np.zeros(4)
        scores[partner[seed]] = 1.0
        return scores

    result = evaluate_rankers({"oracle": oracle, "anti": anti}, graph, [["f0", "f1"]], ks=(1,))
    assert result["pairs"] == 2
    assert result["recall"]["oracle"][1] == 1.0
    assert result["recall"]["anti"][1] == 0.0


def test_evaluate_rankers_empty_history_is_not_a_score() -> None:
    result = evaluate_rankers({"x": lambda s: np.zeros(4)}, _toy_graph(), [], ks=(5,))
    assert result["status"] == "empty"
    assert result["recall"]["x"][5] is None
