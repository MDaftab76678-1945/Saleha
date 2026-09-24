"""
Saleha Core: Repo Context Packer (Aider-style Repository Map)

Packages a token-budgeted, task-relevant architectural slice of the repository
to prepend into LLM coder and planner prompts:

1. Scans workspace files (pruning .git, build, venv, and cache artifacts).
2. Scores each source file against task intent:
   - Path keyword alignment.
   - AST-extracted symbol name density (classes, functions, async methods).
   - Docstring relevance matching.
   - File-path architectural heuristics (core/lib/app prioritized over tests/mocks).
   - Entry-point boosting (main.py, app.py, index.js).
   - Optional (SALEHA_SEMANTIC_CONTEXT=1): semantic similarity from a local
     Ollama embedding model, fused with the keyword ranking by reciprocal
     rank. When it cannot run, `last_ranking_note` says why.
3. Packs a structured context block within model token boundaries:
   - Project directory layout.
   - Ranked symbol outlines.
   - Key file excerpts (multi-file up to configured budget).
"""

from __future__ import annotations

import array
import ast
import base64
import itertools
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from saleha.core.context_budget import chars_budget_for
from saleha.core.path_utils import safe_relpath

# Standard directories to skip during scanning
SKIP_DIRS: Set[str] = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", "venv", ".venv",
    "env", ".env", "dist", "build", ".idea", ".vscode", ".mypy_cache",
    ".pytest_cache", "site-packages", ".tox", "coverage", ".saleha",
    # Framework build output: minified bundles that out-scored every real
    # source file (apps/web/.next chunks took the top six ranks).
    ".next", ".nuxt", ".astro", ".turbo", ".svelte-kit", "out", ".cache",
}

# The popularity boost is task-independent (it counts cross-file references),
# so it only reorders files the task already matched, and never by more than
# about one strong keyword hit.
_POPULARITY_CAP = 3.0

CODE_EXTENSIONS: Set[str] = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rs", ".rb",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".php", ".swift", ".kt",
}

# Semantic ranking: reciprocal-rank-fusion constant, how many semantic
# neighbours may lift a file the keyword scorer gave nothing, and how much of
# each file the embedding model sees (path + symbols + file head).
_RRF_K = 60
_SEMANTIC_TOP_N = 40
_CARD_HEAD_CHARS = 800
_CARD_MAX_CHARS = 2000
_EMBED_CACHE_DIR = ".saleha"

_SYMBOL_RE = re.compile(
    r"^(?:\s*)(?:def|class|func|function|fn|public|private)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def _python_symbols(path: str) -> List[Tuple[int, str, str, str]]:
    """
    Extracts accurate symbols from Python files via the standard AST:
    (lineno, kind, name, first_line_of_docstring).
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return []

    out: List[Tuple[int, str, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        elif isinstance(node, ast.ClassDef):
            kind = "class"
        else:
            continue
        doc = ast.get_docstring(node) or ""
        doc_first = doc.strip().splitlines()[0][:80] if doc.strip() else ""
        out.append((node.lineno, kind, node.name, doc_first))
    return out[:80]


_STOPWORDS: Set[str] = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "with", "on",
    "is", "are", "be", "this", "that", "it", "as", "at", "by", "from",
    "add", "create", "make", "build", "implement", "write", "update", "fix",
}


@dataclass
class ScoredFile:
    path: str
    score: float
    size_chars: int
    symbols: List[str] = field(default_factory=list)          # Display strings
    symbol_tokens: Set[str] = field(default_factory=set)      # Normalized tokens for scoring
    doc_tokens: Set[str] = field(default_factory=set)         # Docstring tokens


def _tokenize(text: str) -> Set[str]:
    """Extracts lowercase words and splits camelCase/snake_case tokens, filtering stopwords."""
    if not text:
        return set()

    # Split camelCase before lowercasing, e.g. "parseConfigFile" -> "parse Config File"
    split_camel = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    # Split on underscores and non-alphanumeric characters, keeping tokens >= 3 chars
    words = re.findall(r"[a-zA-Z0-9]{3,}", split_camel.lower())
    return {w for w in words if w not in _STOPWORDS}



class RepoContextPacker:
    def __init__(
        self,
        root_dir: str = ".",
        max_files: int = 400,
        excerpt_lines: int = 40,
        symbol_ranker: Optional[Any] = None,
        embedder: Optional[Any] = None,
        semantic: Optional[bool] = None,
    ) -> None:
        self.root_dir = os.path.abspath(root_dir)
        self.max_files = max_files
        self.excerpt_lines = excerpt_lines
        self.ranker: Any = symbol_ranker if symbol_ranker is not None else self._default_ranker()
        # `embedder` needs embed_batch(texts) -> normalized vectors or None, and
        # a `model` name. None means "an OllamaEmbedder, created on first use".
        # Opt-in: an explicit embedder, or SALEHA_SEMANTIC_CONTEXT=1. Measured
        # on this repo's own history (commit subject -> files it changed), the
        # fusion won on one sample and lost on a held-out one, so it is not
        # the default until a better file card or weighting beats keywords.
        if semantic is None:
            semantic = embedder is not None or (
                os.environ.get("SALEHA_TEST_MODE") != "1"
                and os.environ.get("SALEHA_SEMANTIC_CONTEXT", "0") == "1"
            )
        self.semantic = semantic
        self.embedder: Optional[Any] = embedder
        # What the most recent rank_files()/pack() actually used, so callers
        # can report it: "keyword" or "keyword+semantic".
        self.last_ranking = "keyword"
        self.last_ranking_note = "semantic ranking disabled" if not semantic else ""

    @staticmethod
    def _default_ranker() -> Optional[Any]:
        try:
            from saleha.core.rag.tree_context_ranker import TreeContextRanker
            ranker = TreeContextRanker()
            return ranker if getattr(ranker, "available", False) else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Scanning & scoring
    # ------------------------------------------------------------------
    def _iter_code_files(self) -> List[str]:
        """Walks the workspace directory and collects readable source code files."""
        found: List[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith((".venv", "venv"))
            ]
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in CODE_EXTENSIONS:
                    continue
                full = os.path.join(dirpath, fname)
                try:
                    if os.path.getsize(full) > 200_000:  # Skip oversized generated artifacts
                        continue
                    with open(full, "r", encoding="utf-8", errors="replace") as f:
                        f.read(400_000)
                    found.append(full)
                    if len(found) >= self.max_files * 4:
                        return found
                except OSError:
                    continue
        return found

    def _score_file(self, path: str, task_tokens: Set[str]) -> Tuple[float, List[str]]:
        """Calculates relevance score and extracts display symbols for a source file."""
        rel = safe_relpath(path, self.root_dir).replace("\\", "/")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return 0.0, []

        ext = os.path.splitext(path)[1].lower()
        display_symbols: List[str] = []
        symbol_name_list: List[str] = []
        doc_list: List[str] = []

        ranker: Any = self.ranker
        if (
            ranker is not None
            and hasattr(ranker, "supported")
            and ranker.supported(ext)
            and hasattr(ranker, "index_file")
            and ranker.index_file(rel, content) is not None
            and hasattr(ranker, "extract_symbols")
        ):
            for (lineno, label) in ranker.extract_symbols(rel, content):
                display_symbols.append(f"{label} (L{lineno})")
                symbol_name_list.append(label.split(" ", 1)[1])

        if not display_symbols and path.lower().endswith(".py"):
            sym_entries = _python_symbols(path)
            for (lineno, kind, name, doc) in sym_entries:
                display_symbols.append(f"{kind} {name} (L{lineno})" if lineno else f"{kind} {name}")
                symbol_name_list.append(name)
                if doc:
                    doc_list.append(doc)

        if not display_symbols:
            names = _SYMBOL_RE.findall(content)[:60]
            display_symbols = [f"def {n}" for n in names]
            symbol_name_list.extend(names)

        symbol_tokens = _tokenize(" ".join(symbol_name_list))
        doc_tokens = _tokenize(" ".join(doc_list))
        content_head = content[:8000]

        score = 0.0
        # 1. Path relevance
        path_tokens = _tokenize(rel)
        score += len(task_tokens & path_tokens) * 3.0
        # 2. Symbol-name relevance (strong signal from AST)
        score += len(task_tokens & symbol_tokens) * 2.5
        # 2b. Docstring relevance
        score += min(len(task_tokens & doc_tokens), 8) * 1.5
        # 3. Content-head overlap (bounded)
        score += min(len(task_tokens & _tokenize(content_head)), 12) * 1.0
        # 4. Path heuristics: production code boosted, tests/fixtures downweighted
        lowered = rel.lower()
        if any(k in lowered for k in ("test", "spec", "fixture", "mock")):
            score *= 0.5
        if any(k in lowered for k in ("src/", "app/", "lib/", "core/", "api/")):
            score *= 1.3
        if lowered.endswith("__init__.py") or lowered.endswith("setup.py"):
            score *= 0.8
        # 5. Application entry points get a boost
        if os.path.basename(lowered) in ("main.py", "index.js", "app.py", "server.py"):
            score += 2.0

        return round(score, 3), display_symbols

    # ------------------------------------------------------------------
    # Semantic ranking
    # ------------------------------------------------------------------
    def _file_card(self, sf: ScoredFile) -> str:
        """Text the embedding model sees for one file: path, symbols, file head."""
        try:
            with open(os.path.join(self.root_dir, sf.path), "r",
                      encoding="utf-8", errors="replace") as f:
                head = f.read(_CARD_HEAD_CHARS)
        except OSError:
            head = ""
        names = ", ".join(s.split(" (L")[0] for s in sf.symbols[:40])
        return f"{sf.path}\n{names}\n{head}"[:_CARD_MAX_CHARS]

    def _cache_path(self, model: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", model)
        return os.path.join(self.root_dir, _EMBED_CACHE_DIR, f"embed_cache_{safe}.json")

    @staticmethod
    def _encode_vec(vec: List[float]) -> str:
        return base64.b64encode(array.array("f", vec).tobytes()).decode("ascii")

    @staticmethod
    def _decode_vec(blob: str) -> List[float]:
        arr = array.array("f")
        arr.frombytes(base64.b64decode(blob))
        return arr.tolist()

    def _load_cache(self, path: str) -> Dict[str, str]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _semantic_scores(self, task: str, scored: List[ScoredFile]) -> Optional[Dict[str, float]]:
        """Cosine similarity of the task to every file, or None if it could not run.

        File vectors are cached on disk under .saleha/, keyed by path, mtime and
        size, so only new or edited files are embedded again.
        """
        if self.embedder is None:
            try:
                from saleha.core.rag.embedding_backends import OllamaEmbedder
                self.embedder = OllamaEmbedder()
            except Exception as exc:  # pragma: no cover - import failure only
                self.last_ranking_note = f"semantic ranking skipped: {exc}"
                return None

        query = self.embedder.embed_batch([task])
        if not query or not query[0]:
            self.last_ranking_note = (
                "semantic ranking skipped: embedding model "
                f"{getattr(self.embedder, 'model', '?')!r} unreachable"
            )
            return None
        qvec = query[0]

        model = str(getattr(self.embedder, "model", "embedder"))
        cache_file = self._cache_path(model)
        cache = self._load_cache(cache_file)
        keys: Dict[str, str] = {}
        missing: List[ScoredFile] = []
        for sf in scored:
            try:
                st = os.stat(os.path.join(self.root_dir, sf.path))
            except OSError:
                continue
            key = f"{sf.path}|{st.st_mtime_ns}|{st.st_size}"
            keys[sf.path] = key
            if key not in cache:
                missing.append(sf)

        if missing:
            vecs = self.embedder.embed_batch([self._file_card(sf) for sf in missing])
            if vecs is None or len(vecs) != len(missing):
                self.last_ranking_note = (
                    f"semantic ranking skipped: embedding {len(missing)} files failed"
                )
                return None
            for sf, vec in zip(missing, vecs, strict=True):
                cache[keys[sf.path]] = self._encode_vec(vec)
            live = set(keys.values())
            cache = {k: v for k, v in cache.items() if k in live}
            try:
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cache, f)
            except OSError as exc:
                # Ranking still ran; only the next call pays the embedding again.
                self.last_ranking_note = f"embedding cache not saved: {exc}"

        sims: Dict[str, float] = {}
        for path, key in keys.items():
            vec = self._decode_vec(cache[key])
            if len(vec) == len(qvec):
                sims[path] = sum(a * b for a, b in zip(qvec, vec, strict=True))
        return sims

    def rank_files(self, task: str) -> List[ScoredFile]:
        """Scores every scanned file against `task`, best first.

        Keyword scoring always runs. When semantic ranking is enabled and the
        embedding model answers, the two rankings are fused by reciprocal
        rank; `last_ranking` / `last_ranking_note` record which one happened.
        """
        self.last_ranking = "keyword"
        if self.semantic:
            self.last_ranking_note = ""
        files = self._iter_code_files()
        task_tokens = _tokenize(task or "")
        scored: List[ScoredFile] = []
        for path in files[: self.max_files * 4]:
            score, symbols = self._score_file(path, task_tokens)
            scored.append(ScoredFile(
                path=safe_relpath(path, self.root_dir).replace("\\", "/"),
                score=score,
                size_chars=os.path.getsize(path),
                symbols=symbols,
            ))

        scored.sort(key=lambda sf: sf.score, reverse=True)

        # Apply popularity boost when ranker is active
        if self.ranker and hasattr(self.ranker, "popularity_boost"):
            try:
                boosts = self.ranker.popularity_boost()
                for sf in scored:
                    if sf.score > 0:
                        sf.score += min(boosts.get(sf.path, 0.0), _POPULARITY_CAP)
                scored.sort(key=lambda sf: sf.score, reverse=True)
            except Exception:
                pass

        if not self.semantic or not scored or not (task or "").strip():
            return scored

        sims = self._semantic_scores(task, scored)
        if sims is None:
            return scored

        # Reciprocal rank fusion. Keyword rank counts only for files the
        # keyword scorer matched; semantic rank only for the nearest
        # _SEMANTIC_TOP_N, so an unrelated file never gets a positive score.
        kw_rank = {sf.path: i for i, sf in enumerate(s for s in scored if s.score > 0)}
        by_sim = sorted(sims, key=lambda p: sims[p], reverse=True)[:_SEMANTIC_TOP_N]
        sem_rank = {p: i for i, p in enumerate(by_sim)}
        for sf in scored:
            fused = 0.0
            if sf.path in kw_rank:
                fused += 1.0 / (_RRF_K + kw_rank[sf.path])
            if sf.path in sem_rank:
                fused += 1.0 / (_RRF_K + sem_rank[sf.path])
            sf.score = round(fused * 1000, 3)
        scored.sort(key=lambda sf: sf.score, reverse=True)
        self.last_ranking = "keyword+semantic"
        return scored

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------
    def pack(
        self,
        task: str,
        budget_chars: Optional[int] = None,
        model: str = "qwen2.5-coder:3b",
        max_excerpts: int = 3,
    ) -> str:
        """
        Packs a task-relevant repository context block bounded by character budget.
        If budget_chars is None, automatically computes a safe character budget
        scaled to the targeted model's context window.
        """
        scored = self.rank_files(task)
        if not scored:
            return ""

        effective_budget: int
        if budget_chars is not None:
            effective_budget = max(1000, budget_chars)
        else:
            effective_budget = chars_budget_for(model, fraction=0.20)
            # Bound dynamic budget between 4,000 and 32,000 characters
            effective_budget = max(4000, min(32000, effective_budget))

        lines: List[str] = ["## Repository Context (auto-packed by Saleha)", ""]
        used = sum(len(line) + 1 for line in lines)

        # --- Section 1: trimmed tree of top-level structure ---
        tree_entries = sorted({
            sf.path.split("/")[0] + ("/" if "/" in sf.path else "")
            for sf in scored
        })[:20]
        tree_block = "### Project Layout\n" + "\n".join(f"- {t}" for t in tree_entries)
        if used + len(tree_block) < effective_budget:
            lines.append(tree_block)
            lines.append("")
            used += len(tree_block) + 2

        # --- Section 2: ranked symbol outlines ---
        outline_budget = int(effective_budget * 0.45)
        outline = ["### Task-Relevant Symbols (ranked)"]
        outline_used = len(outline[0])
        shown = 0
        for sf in scored:
            if sf.score <= 0 or shown >= 25:
                break
            sym_summary = ", ".join(sf.symbols[:8]) if sf.symbols else "(no symbols)"
            entry = f"- {sf.path} :: {sym_summary}"
            if outline_used + len(entry) + 1 > outline_budget:
                break
            outline.append(entry)
            outline_used += len(entry) + 1
            shown += 1
        if shown:
            lines.extend(outline)
            lines.append("")
            used += outline_used + 1

        # --- Section 3: excerpts of top relevant files ---
        excerpts_added = 0
        for sf in scored:
            if sf.score <= 0 or excerpts_added >= max_excerpts:
                break
            remaining = effective_budget - used - 64
            if remaining <= 250:
                break
            try:
                with open(os.path.join(self.root_dir, sf.path), "r",
                          encoding="utf-8", errors="replace") as f:
                    excerpt_lines = [
                        ln.rstrip() for ln in itertools.islice(f, self.excerpt_lines)
                    ]
                excerpt = "\n".join(excerpt_lines)[:remaining]
                lang = "python" if sf.path.endswith(".py") else ""
                section = (
                    f"### Key File Excerpt: {sf.path}\n"
                    f"```{lang}\n"
                    f"{excerpt}\n```"
                )
                if used + len(section) < effective_budget:
                    lines.append(section)
                    lines.append("")
                    used += len(section) + 2
                    excerpts_added += 1
            except OSError:
                pass

        if len(lines) <= 2:  # Only header was generated
            return ""

        return "\n".join(lines).strip()

    def stats(self) -> Dict[str, object]:
        files = self._iter_code_files()
        return {"root": self.root_dir, "code_files": len(files)}


repo_context_packer = RepoContextPacker()

