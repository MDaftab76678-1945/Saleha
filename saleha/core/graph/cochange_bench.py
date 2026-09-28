"""
Saleha Core: co-change benchmark for code-graph embeddings.

Question it answers: given one file a change starts in, which other files
should a small local model get in its context? Here "should" means "were
really changed together", taken from git history -- ground truth that no
method below ever trains on.

For every past commit that touched between 2 and ``max_files`` Python files
still present in the tree, each of those files is used once as the seed and
the rest are the targets. A method ranks every other file by closeness to
the seed; recall@k is the share of targets in its top k.

The graph is the *current* tree: each directory linked to its children,
plus file-to-file import edges. Today's imports were written in those same
commits, so every graph-based method gets that head start equally; ``random``
is the floor that has none.

Methods:
  poincare_<d>, euclidean_<d>  learned embeddings (``poincare_embedding``);
                               the learning rate is chosen on graph
                               reconstruction MAP, never on co-change data
  graph_hops                   BFS hop distance on the same graph, no learning
  random                       uniform shuffle

Run: python -m saleha.core.graph.cochange_bench --repo .
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from saleha.core.graph.poincare_embedding import (
    GEOMETRIES,
    EmbeddingResult,
    distances_from,
    reconstruction_map,
    train_embedding,
)

DEFAULT_KS = (5, 10, 20)


@dataclass
class CodeGraph:
    nodes: List[str]
    index: Dict[str, int]
    edges: List[Tuple[int, int]]
    files: List[str]
    import_edges: int = 0
    skipped: List[Tuple[str, str]] = field(default_factory=list)


def _module_candidates(tree: ast.AST, file_rel: Path) -> List[List[str]]:
    """Each import as an ordered list of dotted names to try, most specific first."""
    package_parts = list(file_rel.parent.parts)
    out: List[List[str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend([alias.name] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(package_parts) - (node.level - 1)
                if keep < 0:
                    continue
                base = package_parts[:keep]
            else:
                base = []
            module = ".".join(base + (node.module.split(".") if node.module else []))
            for alias in node.names:
                # `from pkg import sub` may name a submodule; else it is a symbol of pkg
                names = [f"{module}.{alias.name}" if module else alias.name]
                if module:
                    names.append(module)
                out.append(names)
    return out


def build_code_graph(repo_root: Path, package: str = "saleha") -> CodeGraph:
    """Directory tree plus resolved import edges for ``repo_root/package``.

    A file that cannot be read or parsed stays in the graph (its tree edge
    is real) but contributes no import edges; it is listed in ``skipped``
    so a partial scan never looks complete.
    """
    root = (repo_root / package).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"package directory not found: {root}")
    repo_root = repo_root.resolve()

    files = sorted(
        p.relative_to(repo_root)
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
    )
    nodes: List[str] = []
    index: Dict[str, int] = {}

    def add(name: str) -> int:
        if name not in index:
            index[name] = len(nodes)
            nodes.append(name)
        return index[name]

    edge_set: Set[Tuple[int, int]] = set()
    for rel in files:
        child = add(rel.as_posix())
        parent = rel.parent
        while True:
            parent_id = add(parent.as_posix())
            edge_set.add((parent_id, child))
            if parent.as_posix() == package or parent == parent.parent:
                break
            child, parent = parent_id, parent.parent

    by_module: Dict[str, str] = {}
    for rel in files:
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        by_module[".".join(parts)] = rel.as_posix()

    graph = CodeGraph(nodes, index, [], [f.as_posix() for f in files])
    import_pairs: Set[Tuple[int, int]] = set()
    for rel in files:
        try:
            tree = ast.parse((repo_root / rel).read_text(encoding="utf-8"), filename=str(rel))
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
            graph.skipped.append((rel.as_posix(), f"{type(exc).__name__}: {exc}"))
            continue
        src = index[rel.as_posix()]
        for names in _module_candidates(tree, rel):
            target = next((by_module[n] for n in names if n in by_module), None)
            if target is not None and target != rel.as_posix():
                import_pairs.add((min(src, index[target]), max(src, index[target])))

    graph.import_edges = len(import_pairs - {tuple(sorted(e)) for e in edge_set})
    graph.edges = sorted(edge_set | import_pairs)
    return graph


@dataclass
class CommitHistory:
    commits: List[List[str]]
    total: int
    too_few: int
    too_many: int


def load_cochange_commits(repo_root: Path, known_files: Set[str], max_files: int = 15) -> CommitHistory:
    """Non-merge commits reduced to their files still in ``known_files``."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "log", "--no-merges", "--name-only", "--pretty=format:%x00%H"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git log failed ({proc.returncode}): {proc.stderr.strip()}")

    history = CommitHistory([], 0, 0, 0)
    for chunk in proc.stdout.split("\x00"):
        lines = [ln.strip() for ln in chunk.strip().splitlines() if ln.strip()]
        if not lines:
            continue
        history.total += 1
        touched = sorted({f for f in lines[1:] if f in known_files})
        if len(touched) < 2:
            history.too_few += 1
        elif len(touched) > max_files:
            history.too_many += 1
        else:
            history.commits.append(touched)
    return history


def _hop_ranker(graph: CodeGraph) -> Callable[[int], np.ndarray]:
    adjacency: List[List[int]] = [[] for _ in graph.nodes]
    for a, b in graph.edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    cache: Dict[int, np.ndarray] = {}

    def rank(seed: int) -> np.ndarray:
        if seed not in cache:
            hops = np.full(len(graph.nodes), np.inf)
            hops[seed] = 0
            queue = deque([seed])
            while queue:
                cur = queue.popleft()
                for nxt in adjacency[cur]:
                    if hops[nxt] == np.inf:
                        hops[nxt] = hops[cur] + 1
                        queue.append(nxt)
            cache[seed] = hops
        return cache[seed]

    return rank


def evaluate_rankers(
    rankers: Dict[str, Callable[[int], np.ndarray]],
    graph: CodeGraph,
    commits: Sequence[Sequence[str]],
    ks: Sequence[int] = DEFAULT_KS,
    seed: int = 0,
) -> Dict[str, Any]:
    """Mean recall@k per method over every (commit, seed file) pair.

    Lower score = closer. Ties are broken by one random permutation per
    pair, shared by every method, so a method full of ties (graph_hops,
    random) is neither helped nor hurt by file order. With no pairs the
    recalls are None and status is "empty" -- never 0 or 100%.
    """
    file_ids = np.array([graph.index[f] for f in graph.files])
    rng = np.random.default_rng(seed)
    sums = {name: {k: 0.0 for k in ks} for name in rankers}
    pairs = 0
    for commit in commits:
        ids = [graph.index[f] for f in commit]
        for s in ids:
            targets = set(ids) - {s}
            candidates = file_ids[file_ids != s]
            tiebreak = rng.permutation(len(candidates))
            for name, rank in rankers.items():
                scores = rank(s)[candidates]
                order = candidates[np.lexsort((tiebreak, scores))]
                for k in ks:
                    sums[name][k] += len(targets & set(order[:k].tolist())) / len(targets)
            pairs += 1
    if pairs == 0:
        return {"status": "empty", "pairs": 0, "recall": {n: {k: None for k in ks} for n in rankers}}
    return {
        "status": "ok",
        "pairs": pairs,
        "recall": {n: {k: v / pairs for k, v in by_k.items()} for n, by_k in sums.items()},
    }


def run_benchmark(
    repo_root: Path,
    dims: Sequence[int] = (2, 5, 10, 20),
    lrs: Sequence[float] = (0.03, 0.1, 0.3, 1.0),
    epochs: int = 200,
    max_files: int = 15,
    ks: Sequence[int] = DEFAULT_KS,
    seed: int = 0,
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    say = log or (lambda _msg: None)
    graph = build_code_graph(repo_root)
    history = load_cochange_commits(repo_root, set(graph.files), max_files)
    say(f"graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges "
        f"({graph.import_edges} import), {len(graph.skipped)} files unparsed")
    say(f"commits: {len(history.commits)} used of {history.total} "
        f"({history.too_few} with <2 files, {history.too_many} with >{max_files})")

    rankers: Dict[str, Callable[[int], np.ndarray]] = {
        "random": lambda _s: np.zeros(len(graph.nodes)),
        "graph_hops": _hop_ranker(graph),
    }
    training: List[Dict[str, Any]] = []
    for dim in dims:
        for geometry in GEOMETRIES:
            best: Optional[Tuple[float, EmbeddingResult]] = None
            tried: List[Dict[str, Any]] = []
            for lr in lrs:
                started = time.perf_counter()
                try:
                    result = train_embedding(graph.edges, len(graph.nodes), dim, geometry,
                                             epochs=epochs, lr=lr, seed=seed)
                except RuntimeError as exc:
                    tried.append({"lr": lr, "map": None, "error": str(exc)})
                    continue
                score = reconstruction_map(result.coords, geometry, graph.edges)
                tried.append({"lr": lr, "map": score, "seconds": round(time.perf_counter() - started, 1)})
                if best is None or score > best[0]:
                    best = (score, result)
            name = f"{geometry}_{dim}"
            say(f"{name}: " + ", ".join(
                f"lr={t['lr']} map={t['map']:.3f}" if t["map"] is not None else f"lr={t['lr']} diverged"
                for t in tried))
            training.append({"method": name, "tried": tried,
                             "chosen_lr": best[1].lr if best else None,
                             "map": best[0] if best else None})
            if best is not None:
                coords = best[1].coords
                rankers[name] = lambda s, c=coords, g=geometry: distances_from(c, s, g)

    evaluation = evaluate_rankers(rankers, graph, history.commits, ks, seed)
    return {
        "graph": {"nodes": len(graph.nodes), "edges": len(graph.edges),
                  "import_edges": graph.import_edges, "files": len(graph.files),
                  "skipped": graph.skipped},
        "commits": {"used": len(history.commits), "total": history.total,
                    "too_few": history.too_few, "too_many": history.too_many,
                    "max_files": max_files},
        "training": training,
        "evaluation": evaluation,
        "settings": {"dims": list(dims), "lrs": list(lrs), "epochs": epochs, "seed": seed},
    }


def format_report(report: Dict[str, Any]) -> str:
    evaluation = report["evaluation"]
    recall = evaluation["recall"]
    ks = list(next(iter(recall.values())).keys())
    maps = {t["method"]: t["map"] for t in report["training"]}
    lines = [f"co-change pairs: {evaluation['pairs']} (status: {evaluation['status']})",
             f"{'method':<16}{'graph MAP':>10}" + "".join(f"{'R@' + str(k):>8}" for k in ks)]
    for name, by_k in recall.items():
        map_text = f"{maps[name]:.3f}" if maps.get(name) is not None else "-"
        cells = "".join(f"{v:>8.3f}" if v is not None else f"{'n/a':>8}" for v in by_k.values())
        lines.append(f"{name:<16}{map_text:>10}{cells}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default=".")
    parser.add_argument("--dims", default="2,5,10,20")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--max-files", type=int, default=15)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json", help="also write the full report here")
    args = parser.parse_args(argv)

    report = run_benchmark(Path(args.repo), dims=[int(d) for d in args.dims.split(",")],
                           epochs=args.epochs, max_files=args.max_files, seed=args.seed,
                           log=print)
    print(format_report(report))
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["evaluation"]["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
