"""
Saleha Core: Polyglot Multi-Language Codebase Indexer

Extracts functions, classes, methods, structs, interfaces, and imports across
multiple languages: Python, JavaScript/TypeScript, Go, Java, Rust, HTML, CSS.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any
from saleha.core.path_utils import safe_relpath


@dataclass
class CodeSymbol:
    name: str
    symbol_type: str  # "class", "function", "method", "interface", "struct", "import"
    language: str
    file_path: str
    line_number: int
    docstring: str = ""
    signature: str = ""


@dataclass
class PolyglotFileSummary:
    file_path: str
    language: str
    lines_of_code: int
    symbols: List[CodeSymbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)


class PolyglotIndexer:
    """Indexes codebase symbols across multiple programming languages."""

    EXT_TO_LANG = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".java": "java",
        ".rs": "rust",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".sql": "sql",
        ".sh": "bash",
    }

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)
        self.files: Dict[str, PolyglotFileSummary] = {}

    def detect_language(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        return self.EXT_TO_LANG.get(ext, "unknown")

    def index_file(self, file_path: str) -> Optional[PolyglotFileSummary]:
        if not os.path.isfile(file_path):
            return None
        lang = self.detect_language(file_path)
        if lang == "unknown":
            return None

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return None

        lines = content.splitlines()
        summary = PolyglotFileSummary(
            file_path=safe_relpath(file_path, self.root_dir),
            language=lang,
            lines_of_code=len(lines),
        )

        # Parse language-specific symbols
        if lang in ("javascript", "typescript"):
            self._parse_js_ts(lines, summary)
        elif lang == "go":
            self._parse_go(lines, summary)
        elif lang == "java":
            self._parse_java(lines, summary)
        elif lang == "rust":
            self._parse_rust(lines, summary)
        elif lang == "python":
            self._parse_python(lines, summary)

        self.files[summary.file_path] = summary
        return summary

    def _parse_js_ts(self, lines: List[str], summary: PolyglotFileSummary):
        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            # Imports
            if sline.startswith("import ") or sline.startswith("const ") and "require(" in sline:
                summary.imports.append(sline)
            # Classes / Interfaces
            m_class = re.match(r"^(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_$]+)", sline)
            if m_class:
                summary.symbols.append(CodeSymbol(
                    name=m_class.group(1), symbol_type="class", language=summary.language,
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))
            m_iface = re.match(r"^(?:export\s+)?interface\s+([A-Za-z0-9_$]+)", sline)
            if m_iface:
                summary.symbols.append(CodeSymbol(
                    name=m_iface.group(1), symbol_type="interface", language=summary.language,
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))
            # Functions
            m_func = re.match(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)", sline)
            if m_func:
                summary.symbols.append(CodeSymbol(
                    name=m_func.group(1), symbol_type="function", language=summary.language,
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))
            m_arrow = re.match(r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", sline)
            if m_arrow:
                summary.symbols.append(CodeSymbol(
                    name=m_arrow.group(1), symbol_type="function", language=summary.language,
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))

    def _parse_go(self, lines: List[str], summary: PolyglotFileSummary):
        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            if sline.startswith("import "):
                summary.imports.append(sline)
            # Struct / Interface
            m_type = re.match(r"^type\s+([A-Za-z0-9_]+)\s+(struct|interface)", sline)
            if m_type:
                summary.symbols.append(CodeSymbol(
                    name=m_type.group(1), symbol_type=m_type.group(2), language="go",
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))
            # Functions / Methods
            m_func = re.match(r"^func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)\s*\(", sline)
            if m_func:
                summary.symbols.append(CodeSymbol(
                    name=m_func.group(1), symbol_type="function", language="go",
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))

    def _parse_java(self, lines: List[str], summary: PolyglotFileSummary):
        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            if sline.startswith("import "):
                summary.imports.append(sline)
            # Class / Interface / Enum
            m_class = re.match(r"^(?:public|protected|private)?\s*(?:static\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+([A-Za-z0-9_]+)", sline)
            if m_class and not sline.startswith("import"):
                summary.symbols.append(CodeSymbol(
                    name=m_class.group(1), symbol_type="class", language="java",
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))
            # Methods
            m_method = re.match(r"^(?:public|protected|private)\s+(?:static\s+)?[A-Za-z0-9_<>\[\]]+\s+([A-Za-z0-9_]+)\s*\([^;]*\)\s*(?:throws\s+[A-Za-z0-9_,\s]+)?\s*\{?$", sline)
            if m_method and m_method.group(1) not in ("class", "if", "for", "while", "switch"):
                summary.symbols.append(CodeSymbol(
                    name=m_method.group(1), symbol_type="method", language="java",
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))

    def _parse_rust(self, lines: List[str], summary: PolyglotFileSummary):
        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            if sline.startswith("use "):
                summary.imports.append(sline)
            m_struct = re.match(r"^(?:pub\s+)?(?:struct|enum|trait)\s+([A-Za-z0-9_]+)", sline)
            if m_struct:
                summary.symbols.append(CodeSymbol(
                    name=m_struct.group(1), symbol_type="struct", language="rust",
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))
            m_fn = re.match(r"^(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]+)\s*\(", sline)
            if m_fn:
                summary.symbols.append(CodeSymbol(
                    name=m_fn.group(1), symbol_type="function", language="rust",
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))

    def _parse_python(self, lines: List[str], summary: PolyglotFileSummary):
        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            if sline.startswith("import ") or sline.startswith("from "):
                summary.imports.append(sline)
            m_class = re.match(r"^class\s+([A-Za-z0-9_]+)", sline)
            if m_class:
                summary.symbols.append(CodeSymbol(
                    name=m_class.group(1), symbol_type="class", language="python",
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))
            m_def = re.match(r"^(?:async\s+)?def\s+([A-Za-z0-9_]+)\s*\(", sline)
            if m_def:
                summary.symbols.append(CodeSymbol(
                    name=m_def.group(1), symbol_type="function", language="python",
                    file_path=summary.file_path, line_number=idx, signature=sline
                ))

    def scan_directory(self, directory: Optional[str] = None) -> Dict[str, Any]:
        """Scans directory (or root_dir) and returns aggregated polyglot symbols and metrics."""
        scan_dir = os.path.abspath(directory) if directory else self.root_dir
        self.files.clear()
        lang_counts: Dict[str, int] = {}
        total_loc = 0
        total_symbols = 0

        for root, _, files in os.walk(scan_dir):
            rel_parts = safe_relpath(root, scan_dir).split(os.sep)
            if any((p.startswith(".") and p not in (".", "..")) or p in ("node_modules", "venv", "__pycache__", "build", "dist", "target", "vendor") for p in rel_parts):
                continue
            for f in files:
                fpath = os.path.join(root, f)
                summary = self.index_file(fpath)
                if summary:
                    lang_counts[summary.language] = lang_counts.get(summary.language, 0) + 1
                    total_loc += summary.lines_of_code
                    total_symbols += len(summary.symbols)

        return {
            "total_files": len(self.files),
            "total_loc": total_loc,
            "total_symbols": total_symbols,
            "languages": lang_counts,
            "files": {path: {
                "language": s.language,
                "loc": s.lines_of_code,
                "symbols_count": len(s.symbols),
                "symbols": [sym.name for sym in s.symbols[:10]]
            } for path, s in self.files.items()}
        }

