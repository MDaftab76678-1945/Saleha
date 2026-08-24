"""
Saleha Core: Repo Context Packer (Aider-style Repository Map)

LLM ko poora repo bhejna impossible hai -- budget hota hai. Ye module:

1. Repo scan karta hai (venv/node_modules/.git skip)
2. Har file ko TASK ke against score karta hai:
   - keyword overlap (task tokens vs path + content head + symbol names)
   - path heuristics (src/app code > tests > docs > configs)
   - symbol density (class/def names task se match)
3. Budget ke andar ek structured context block pack karta hai:
   project tree (trimmed) -> relevant symbol outlines -> key-file excerpts

Output seedha Coder/Planner prompt me prepend hota hai taaki generated code
real repo ke conventions, existing types, aur module structure ka respect kare.
Ye Aider ke repo-map idea ka lightweight, zero-dependency version hai.
"""

import ast
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from saleha.core.path_utils import safe_relpath

# Skip dirs -- indexer conventions se aligned
SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", "venv", ".venv",
    "env", ".env", "dist", "build", ".idea", ".vscode", ".mypy_cache",
    ".pytest_cache", "site-packages", ".tox", "coverage", ".saleha",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rs", ".rb",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".php", ".swift", ".kt",
}

_SYMBOL_RE = re.compile(
    r"^(?:\s*)(?:def|class|func|function|fn|public|private)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def _python_symbols(path: str) -> List[Tuple[int, str, str, str]]:
    """AST-accurate symbol extraction (A3 upgrade): (lineno, kind, name,
    docstring-first-line). Regex fallback se better -- nested defs, async
    functions, aur decorators sahi pakde jaate hain, line numbers milte hain."""
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

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "with", "on",
    "is", "are", "be", "this", "that", "it", "as", "at", "by", "from",
    "add", "create", "make", "build", "implement", "write", "update", "fix",
}


@dataclass
class ScoredFile:
    path: str
    score: float
    size_chars: int
    symbols: List[str] = field(default_factory=list)          # display strings
    symbol_tokens: set = field(default_factory=set)           # for scoring
    doc_tokens: set = field(default_factory=set)              # docstring tokens


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
    return {w for w in words if w not in _STOPWORDS} | {
        # camelCase / snake_case split: "parseConfigFile" -> parse config file
        part
        for w in words
        for part in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", w)
        if len(part) >= 3
    }


class RepoContextPacker:
    def __init__(self, root_dir: str = ".", max_files: int = 400,
                 excerpt_lines: int = 40,
                 symbol_ranker: Optional[object] = None):
        self.root_dir = os.path.abspath(root_dir)
        self.max_files = max_files
        self.excerpt_lines = excerpt_lines
        # B1.5: tree-sitter ranker -- diya gaya to use karo, warna ek hi baar
        # lazy probe (grammars installed na hon to False -> legacy path)
        if symbol_ranker is not None:
            self.ranker = symbol_ranker
        else:
            self.ranker = self._default_ranker()

    @staticmethod
    def _default_ranker():
        try:
            from saleha.core.tree_context_ranker import TreeContextRanker
            ranker = TreeContextRanker()
            return ranker if ranker.available else False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Scanning & scoring
    # ------------------------------------------------------------------
    def _iter_code_files(self) -> List[str]:
        found: List[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in CODE_EXTENSIONS:
                    continue
                full = os.path.join(dirpath, fname)
                try:
                    if os.path.getsize(full) > 200_000:  # huge generated files skip
                        continue
                    with open(full, "r", encoding="utf-8", errors="replace") as f:
                        f.read(400_000)
                    found.append(full)
                    if len(found) >= self.max_files * 4:
                        return found
                except OSError:
                    continue
        return found

    def _score_file(self, path: str, task_tokens: set) -> Tuple[float, List[str]]:
        rel = safe_relpath(path, self.root_dir).replace("\\", "/")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return 0.0, []

        # A3+C: symbol extraction priority --
        #   1) tree-sitter ranker (multi-lang, jab [codeintel] extra installed ho)
        #   2) Python built-in ast
        #   3) regex fallback (baaki languages)
        ext = os.path.splitext(path)[1].lower()
        display_symbols: List[str] = []
        symbol_name_list: List[str] = []
        doc_list: List[str] = []

        ranker = self.ranker or None
        if ranker is not None and ranker.supported(ext):
            if ranker.index_file(rel, content) is not None:
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
        # 2. Symbol-name relevance (sabse strong signal -- AST-accurate ab)
        score += len(task_tokens & symbol_tokens) * 2.5
        # 2b. Docstring relevance (naya: "rate limiter" jaisa task docstring se match)
        score += min(len(task_tokens & doc_tokens), 8) * 1.5
        # 3. Content-head overlap (bounded)
        score += min(len(task_tokens & _tokenize(content_head)), 12) * 1.0
        # 4. Path heuristics: production code up, tests/docs down
        lowered = rel.lower()
        if any(k in lowered for k in ("test", "spec", "fixture", "mock")):
            score *= 0.5
        if any(k in lowered for k in ("src/", "app/", "lib/", "core/", "api/")):
            score *= 1.3
        if lowered.endswith("__init__.py") or lowered.endswith("setup.py"):
            score *= 0.8
        # 5. Entry points get a small boost
        if os.path.basename(lowered) in ("main.py", "index.js", "app.py", "server.py"):
            score += 2.0

        return round(score, 3), display_symbols

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------
    def pack(self, task: str, budget_chars: int = 6000) -> str:
        """Task-relevant repo context block return karta hai (budget-bound).
        Empty repo par empty string."""
        files = self._iter_code_files()
        if not files:
            return ""

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

        # C+: tree-sitter hub-popularity boost (jab ranker available ho) --
        # shared symbols define karne wali "hub" files ko up-rank karta hai.
        if self.ranker:
            try:
                boosts = self.ranker.popularity_boost()
                for sf in scored:
                    sf.score += boosts.get(sf.path, 0.0)
                scored.sort(key=lambda sf: sf.score, reverse=True)
            except Exception:
                pass

        lines: List[str] = ["## Repository Context (auto-packed by Saleha)", ""]
        used = sum(len(l) + 1 for l in lines)

        # --- Section 1: trimmed tree of top-level structure ---
        tree_entries = sorted({
            sf.path.split("/")[0] + ("/" if "/" in sf.path else "")
            for sf in scored
        })[:20]
        tree_block = "### Project Layout\n" + "\n".join(f"- {t}" for t in tree_entries)
        if used + len(tree_block) < budget_chars:
            lines.append(tree_block)
            lines.append("")
            used += len(tree_block) + 2

        # --- Section 2: ranked symbol outlines ---
        outline_budget = int(budget_chars * 0.45)
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

        # --- Section 3: excerpt of the single most relevant file ---
        for sf in scored:
            if sf.score <= 0:
                break
            remaining = budget_chars - used - 64
            if remaining <= 200:
                break
            try:
                with open(os.path.join(self.root_dir, sf.path), "r",
                          encoding="utf-8", errors="replace") as f:
                    excerpt_lines = [
                        ln.rstrip() for i, ln in zip(range(self.excerpt_lines), f)
                    ]
                excerpt = "\n".join(excerpt_lines)[:remaining]
                section = (
                    f"### Key File Excerpt: {sf.path}\n"
                    f"```{'python' if sf.path.endswith('.py') else ''}\n"
                    f"{excerpt}\n```"
                )
                if used + len(section) < budget_chars:
                    lines.append(section)
            except OSError:
                pass
            break  # sirf top-1 file ka excerpt (budget discipline)

        if len(lines) == 2:  # sirf header bana
            return ""

        return "\n".join(lines)

    def stats(self) -> Dict[str, object]:
        files = self._iter_code_files()
        return {"root": self.root_dir, "code_files": len(files)}
