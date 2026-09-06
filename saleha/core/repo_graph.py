"""
Saleha Core: Real cross-file repository graph (graphify-backed)

Why this exists
---------------
Saleha already had several indexers, but the one question that matters most
for an autonomous agent -- "if I change X, what else is affected?" -- was
not actually answered. Measured on this repo:

    CodebaseDependencyGraph.get_impacted_files("agentic_loop.py")  ->  []

while the real answer is six files (saleha/cli/commands/__init__.py,
cli/commands/core_agentic.py, core/loop/__init__.py, core/swe_bench_runner.py,
server/web_server.py, tests/test_agentic_loop.py). Our own graph resolved
call edges within a file but never resolved cross-file imports, so it
reported "nothing depends on this" for a module six other files import.

This module wraps `graphify` (tree-sitter based, 37 languages, fully local
-- code extraction needs no API key and nothing leaves the machine) to
provide the cross-file view. Measured on this repo: 572 files -> 7,459
nodes / 16,484 edges in ~12s, with real `imports`, `calls`, `inherits`,
`references` and `uses` relations.

Deliberate limitation, stated plainly
-------------------------------------
This is *static* analysis. Saleha's CLI imports many modules lazily (inside
a function body), and a lazy import is still a real dependency that a
static scan can miss. So `importers_of()` returning an empty list means
"no static import found", NOT "this module is dead". `find_unused_modules()`
is therefore named and documented as a *candidate* list for human review --
deleting from it blindly would break working code.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

DEFAULT_EXCLUDES = {
    "__pycache__", ".git", "node_modules", "target", ".next", ".venv",
    ".venv_train", "build", "dist", ".pytest_cache", "graphify-out",
    ".claude", "saleha.egg-info", ".astro",
}

CODE_SUFFIXES = {
    ".py", ".rs", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rb",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".kt", ".php", ".swift", ".lua",
    ".zig", ".ex", ".sol", ".sql", ".sh", ".ps1",
}


def graphify_available() -> bool:
    """True if the optional graphify dependency is importable."""
    try:
        import graphify.extract  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass
class GraphStats:
    files_scanned: int = 0
    nodes: int = 0
    edges: int = 0
    build_seconds: float = 0.0
    relations: Dict[str, int] = field(default_factory=dict)


class RepoGraph:
    """
    Cross-file repository graph over a real codebase.

    Build once, then ask real questions:

        g = RepoGraph("/path/to/repo")
        g.build()
        g.importers_of("saleha/core/agentic_loop.py")   # who breaks if I change it
        g.neighbors_of("AgentLoop")                     # what this touches
    """

    def __init__(self, root_dir: str = ".",
                 excludes: Optional[Set[str]] = None,
                 suffixes: Optional[Set[str]] = None):
        self.root = Path(os.path.abspath(root_dir))
        self.excludes = set(excludes) if excludes is not None else set(DEFAULT_EXCLUDES)
        self.suffixes = set(suffixes) if suffixes is not None else set(CODE_SUFFIXES)
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.stats = GraphStats()
        self._built = False

    # -- discovery -----------------------------------------------------
    def discover_files(self) -> List[Path]:
        """Real source files under root, skipping build/vendor noise."""
        out: List[Path] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in self.excludes]
            for fn in filenames:
                if Path(fn).suffix.lower() in self.suffixes:
                    out.append(Path(dirpath) / fn)
        return sorted(out)

    # -- build ---------------------------------------------------------
    def build(self, files: Optional[Iterable[Path]] = None,
              parallel: bool = False) -> GraphStats:
        """
        Extract the real graph. Raises ImportError with a clear message if
        graphify isn't installed, rather than silently returning an empty
        graph that would read as "nothing depends on anything".

        parallel defaults to False: graphify's process pool needs an
        ``if __name__ == "__main__"`` guard in the caller on Windows and
        otherwise falls back with a warning, which is noisy when Saleha
        calls this from inside a command.
        """
        if not graphify_available():
            raise ImportError(
                "repo_graph requires the optional 'graphifyy' package "
                "(pip install graphifyy). Code extraction runs fully local; "
                "no API key is needed."
            )
        from graphify.extract import extract

        paths = list(files) if files is not None else self.discover_files()
        t0 = time.time()
        data = extract(paths, root=self.root, cache_root=self.root,
                       parallel=parallel)
        elapsed = time.time() - t0

        self.nodes = list(data.get("nodes") or [])
        self.edges = list(data.get("edges") or [])
        relations: Dict[str, int] = {}
        for e in self.edges:
            rel = str(e.get("relation") or "unknown")
            relations[rel] = relations.get(rel, 0) + 1

        self.stats = GraphStats(
            files_scanned=len(paths), nodes=len(self.nodes),
            edges=len(self.edges), build_seconds=round(elapsed, 2),
            relations=dict(sorted(relations.items(), key=lambda kv: -kv[1])),
        )
        self._built = True
        return self.stats

    def _require_built(self) -> None:
        if not self._built:
            raise RuntimeError("call build() before querying the graph")

    # -- queries -------------------------------------------------------
    @staticmethod
    def _module_key(path_or_name: str) -> str:
        """'saleha/core/agentic_loop.py' -> 'agentic_loop' (the stem)."""
        s = str(path_or_name).replace("\\", "/").strip()
        if "/" in s or s.endswith(".py"):
            s = Path(s).stem
        return s

    def importers_of(self, module: str) -> List[str]:
        """
        Real source files that statically import `module`.

        Accepts a path ('saleha/core/agentic_loop.py') or a bare module
        name ('agentic_loop'). An empty result means "no static import
        found" -- see the module docstring on lazy imports.
        """
        self._require_built()
        key = self._module_key(module)
        found: Set[str] = set()
        for e in self.edges:
            if str(e.get("relation") or "") not in ("imports", "imports_from",
                                                    "dynamic_import", "re_exports"):
                continue
            target = str(e.get("target") or "")
            if target.endswith(key) or f"_{key}" in target:
                src = e.get("source_file")
                if src:
                    found.add(str(src).replace("\\", "/"))
        # A module importing itself is not an external dependant.
        self_path = None
        for n in self.nodes:
            sf = str(n.get("source_file") or "").replace("\\", "/")
            if Path(sf).stem == key:
                self_path = sf
                break
        found.discard(self_path or "")
        return sorted(found)

    def neighbors_of(self, symbol: str, limit: int = 50) -> List[Dict[str, str]]:
        """Real edges touching a symbol/module, in both directions."""
        self._require_built()
        key = symbol.lower()
        out: List[Dict[str, str]] = []
        for e in self.edges:
            src, tgt = str(e.get("source") or ""), str(e.get("target") or "")
            if key in src.lower() or key in tgt.lower():
                out.append({
                    "source": src,
                    "relation": str(e.get("relation") or "unknown"),
                    "target": tgt,
                    "at": f"{e.get('source_file')}:{e.get('source_location')}",
                })
                if len(out) >= limit:
                    break
        return out

    def find_unused_module_candidates(self, package_dir: str = "") -> List[str]:
        """
        Modules with no static importer -- a *review candidate* list, not a
        delete list. Saleha's CLI imports many modules lazily inside
        function bodies, which static extraction cannot see, so entries
        here must be verified before anything is removed.
        """
        self._require_built()
        base = self.root / package_dir if package_dir else self.root
        candidates: List[str] = []
        for py in sorted(base.rglob("*.py")):
            if any(part in self.excludes for part in py.parts):
                continue
            if py.name == "__init__.py":
                continue
            rel = str(py.relative_to(self.root)).replace("\\", "/")
            if not self.importers_of(rel):
                candidates.append(rel)
        return candidates

    def summary(self) -> Dict[str, Any]:
        self._require_built()
        return {
            "root": str(self.root),
            "files_scanned": self.stats.files_scanned,
            "nodes": self.stats.nodes,
            "edges": self.stats.edges,
            "build_seconds": self.stats.build_seconds,
            "relations": self.stats.relations,
        }
