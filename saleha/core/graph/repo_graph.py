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

import json
import os
import time
from dataclasses import asdict, dataclass, field
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


STORE_VERSION = 1
STORE_RELATIVE_PATH = Path(".saleha") / "repo_graph.json"


def graphify_available() -> bool:
    """True if the graphify dependency is importable (a core dependency)."""
    try:
        import graphify.extract  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass
class GraphStats:
    """Real counts from one graph build.

    `files_scanned` is how many files were handed to the extractor, which is
    not the same as how many are actually represented in the graph: a file
    whose language grammar is not installed, or one the parser chokes on,
    contributes nothing and would otherwise be indistinguishable from a file
    with genuinely no symbols. `files_with_symbols` and `files_absent` make
    that gap visible instead of letting `files_scanned` imply full coverage.
    """

    files_scanned: int = 0
    files_with_symbols: int = 0
    files_absent: List[str] = field(default_factory=list)
    nodes: int = 0
    edges: int = 0
    build_seconds: float = 0.0
    relations: Dict[str, int] = field(default_factory=dict)
    # Where this graph came from: "built" (extracted just now) or "store"
    # (read back from disk after the manifest proved no source file changed).
    # `reason` says why it was rebuilt when it was not loaded.
    source: str = "built"
    reason: str = ""
    saved: bool = False
    save_error: str = ""

    @property
    def coverage_is_complete(self) -> bool:
        """True only if every scanned file contributed at least one symbol."""
        return not self.files_absent


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
                 suffixes: Optional[Set[str]] = None) -> None:
        self.root = Path(os.path.abspath(root_dir))
        self.excludes = set(excludes) if excludes is not None else set(DEFAULT_EXCLUDES)
        self.suffixes = set(suffixes) if suffixes is not None else set(CODE_SUFFIXES)
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.stats = GraphStats()
        self._built = False
        # Per-file (mtime_ns, size) of what the current graph was built from,
        # and whether that was a full discovery scan. Only a full-scan graph
        # may be persisted: a partial graph saved as "the repo graph" would
        # read as full coverage on the next load.
        self._manifest: Dict[str, List[int]] = {}
        self._full_scan = False

    # -- discovery -----------------------------------------------------
    def discover_files(self) -> List[Path]:
        """Real source files under root, skipping build/vendor noise."""
        out: List[Path] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Any virtualenv, whatever it is called (.venv, .venv_train,
            # .venv_laya ...): an unlisted one put ~30k library files into the
            # scan and the build never finished.
            dirnames[:] = [d for d in dirnames
                           if d not in self.excludes
                           and not (Path(dirpath, d) / "pyvenv.cfg").is_file()]
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
                "repo_graph needs the 'graphifyy' package, which is a core "
                "Saleha dependency -- this install is broken; reinstall with "
                "`pip install -e .`. Code extraction runs fully local; "
                "no API key is needed."
            )
        from graphify.extract import extract

        paths = list(files) if files is not None else self.discover_files()
        # Taken before extraction: a file edited mid-build then shows up as
        # changed on the next load instead of being recorded as current.
        manifest = self._manifest_of(paths)
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

        # A file the extractor could not parse (missing language grammar, or a
        # construct its grammar rejects) yields no nodes at all. Counting it
        # under files_scanned alone would report full coverage over a graph
        # that is silently missing that file's symbols.
        represented: Set[str] = set()
        for n in self.nodes:
            src = n.get("source_file")
            if src:
                represented.add(str(src).replace("\\", "/"))

        # Deduplicated: the same path passed twice is one file, not two, so
        # counting raw `paths` would inflate both totals.
        scanned_keys: Set[str] = set()
        for p in paths:
            abs_p = Path(p).resolve()
            try:
                key = str(abs_p.relative_to(self.root))
            except ValueError:
                # Outside root: keep the absolute path, but normalised the same
                # way so every entry in files_absent reads consistently.
                key = str(abs_p)
            scanned_keys.add(key.replace("\\", "/"))

        absent = sorted(k for k in scanned_keys if k not in represented)

        self.stats = GraphStats(
            files_scanned=len(scanned_keys),
            files_with_symbols=len(scanned_keys) - len(absent),
            files_absent=absent,
            nodes=len(self.nodes),
            edges=len(self.edges), build_seconds=round(elapsed, 2),
            relations=dict(sorted(relations.items(), key=lambda kv: -kv[1])),
        )
        self._manifest = manifest
        self._full_scan = files is None
        self._built = True
        return self.stats

    # -- persistence ---------------------------------------------------
    def store_path(self) -> Path:
        """Where this repo's graph lives: <root>/.saleha/repo_graph.json."""
        return self.root / STORE_RELATIVE_PATH

    def _manifest_of(self, paths: Iterable[Path]) -> Dict[str, List[int]]:
        """(mtime_ns, size) per file, keyed by root-relative posix path.

        A file that cannot be stat'ed is recorded as [-1, -1], so it differs
        from any real stat and forces a rebuild rather than being skipped.
        """
        out: Dict[str, List[int]] = {}
        for p in paths:
            abs_p = Path(p).resolve()
            try:
                key = str(abs_p.relative_to(self.root))
            except ValueError:
                key = str(abs_p)
            try:
                st = abs_p.stat()
                out[key.replace("\\", "/")] = [st.st_mtime_ns, st.st_size]
            except OSError:
                out[key.replace("\\", "/")] = [-1, -1]
        return out

    def changed_files(self, stored: Dict[str, List[int]]) -> List[str]:
        """Files added, removed or modified since `stored` was recorded."""
        current = self._manifest_of(self.discover_files())
        keys = set(current) | set(stored)
        return sorted(k for k in keys if current.get(k) != stored.get(k))

    def save(self, path: Optional[Path] = None) -> Path:
        """Write the built graph to disk atomically and return where.

        Raises RuntimeError for a graph that was not built from a full
        discovery scan, and lets OSError/TypeError through: a failed save must
        be visible to the caller, never reported as saved.
        """
        self._require_built()
        if not self._full_scan:
            raise RuntimeError(
                "refusing to persist a partial graph (build() was given an "
                "explicit file list); only a full scan may be saved")
        dest = Path(path) if path is not None else self.store_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": STORE_VERSION,
            "root": str(self.root),
            "saved_at": time.time(),
            "manifest": self._manifest,
            "stats": asdict(self.stats),
            "nodes": self.nodes,
            "edges": self.edges,
        }
        tmp = dest.with_name(dest.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, dest)
        return dest

    def load(self, path: Optional[Path] = None) -> str:
        """Load a saved graph if it is still valid. Returns "" on success,
        otherwise the reason it was NOT loaded (missing, unreadable, wrong
        version, other repo, or which source files changed).

        Never returns a graph that is out of date with the files on disk.
        """
        src = Path(path) if path is not None else self.store_path()
        if not src.is_file():
            return "no saved graph"
        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("top level is not an object")
            if data.get("version") != STORE_VERSION:
                return f"saved graph has version {data.get('version')!r}, expected {STORE_VERSION}"
            if data.get("root") != str(self.root):
                return "saved graph was built for a different root"
            manifest = data["manifest"]
            nodes, edges, stats = data["nodes"], data["edges"], data["stats"]
            if not (isinstance(manifest, dict) and isinstance(nodes, list)
                    and isinstance(edges, list) and isinstance(stats, dict)):
                raise ValueError("wrong field types")
        except (OSError, ValueError, KeyError) as err:
            return f"saved graph unreadable: {err}"

        changed = self.changed_files(manifest)
        if changed:
            head = ", ".join(changed[:3])
            more = f" (+{len(changed) - 3} more)" if len(changed) > 3 else ""
            return f"{len(changed)} source file(s) changed since save: {head}{more}"

        self.nodes, self.edges = nodes, edges
        self._manifest = manifest
        self._full_scan = True
        known = {k: v for k, v in stats.items() if k in GraphStats.__dataclass_fields__}
        self.stats = GraphStats(**known)
        self.stats.source = "store"
        self.stats.reason = ""
        self._built = True
        return ""

    def load_or_build(self, rebuild: bool = False) -> GraphStats:
        """The one entry point for callers: reuse the saved graph when the
        sources are unchanged, otherwise extract fresh and save it.

        `stats.source` says which happened; `stats.reason` says why a rebuild
        was needed; `stats.saved` / `stats.save_error` say whether the fresh
        graph reached disk. A failed save does not fail the build.
        """
        reason = "rebuild requested" if rebuild else self.load()
        if not reason:
            return self.stats
        stats = self.build()
        stats.reason = reason
        try:
            self.save()
            stats.saved = True
        except (OSError, TypeError, ValueError, RuntimeError) as err:
            stats.saved = False
            stats.save_error = str(err)
        return stats

    def _require_built(self) -> None:
        if not self._built:
            raise RuntimeError("call build() before querying the graph")

    # -- queries -------------------------------------------------------
    @staticmethod
    def _module_key(path_or_name: str) -> str:
        """'saleha/core/agentic_loop.py' -> 'agentic_loop' (the stem)."""
        s = path_or_name.replace("\\", "/").strip()
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
