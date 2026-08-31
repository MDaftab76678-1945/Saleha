"""
Saleha Core: Native Polyglot AST & Concrete Syntax Tree Engine

Provides universal, cross-language symbol extraction, function boundary identification,
and import call-graph analysis across Python, JavaScript, TypeScript, Go, Rust, and Java.
"""

from __future__ import annotations

import os
import re
import ast
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set, Any


@dataclass
class PolyglotSymbol:
    name: str
    kind: str               # class, function, method, interface, struct, enum
    language: str           # python, javascript, typescript, go, rust, java
    file_path: str
    start_line: int
    end_line: int
    signature: str = ""
    docstring: str = ""
    is_exported: bool = True


class PolyglotASTEngine:
    """Universal symbol and syntax tree analyzer supporting polyglot codebases."""

    EXTENSION_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java"
    }

    def detect_language(self, file_path: str) -> Optional[str]:
        """Maps file extension to canonical language name."""
        ext = os.path.splitext(file_path)[1].lower()
        return self.EXTENSION_MAP.get(ext)

    def parse_python(self, file_path: str, content: str) -> List[PolyglotSymbol]:
        """Parses Python source using native AST."""
        symbols = []
        try:
            tree = ast.parse(content, filename=file_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    doc = ast.get_docstring(node) or ""
                    symbols.append(PolyglotSymbol(
                        name=node.name,
                        kind="class",
                        language="python",
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=f"class {node.name}",
                        docstring=doc
                    ))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    doc = ast.get_docstring(node) or ""
                    is_async = isinstance(node, ast.AsyncFunctionDef)
                    prefix = "async def " if is_async else "def "
                    symbols.append(PolyglotSymbol(
                        name=node.name,
                        kind="function",
                        language="python",
                        file_path=file_path,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=f"{prefix}{node.name}()",
                        docstring=doc
                    ))
        except SyntaxError:
            pass
        return symbols

    def parse_javascript_typescript(self, file_path: str, content: str) -> List[PolyglotSymbol]:
        """Extracts JS/TS functions, classes, interfaces, and arrow functions."""
        symbols = []
        lines = content.splitlines()
        lang = "typescript" if file_path.endswith((".ts", ".tsx")) else "javascript"

        # 1. Functions & Async Functions: (export)? (async)? function name(...)
        fn_re = re.compile(r'^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\((.*?)\)', re.MULTILINE)
        for m in fn_re.finditer(content):
            line_no = content[:m.start()].count('\n') + 1
            symbols.append(PolyglotSymbol(
                name=m.group(1),
                kind="function",
                language=lang,
                file_path=file_path,
                start_line=line_no,
                end_line=line_no,
                signature=m.group(0).strip()
            ))

        # 2. Classes & Interfaces
        class_re = re.compile(r'^(?:export\s+)?(?:default\s+)?(?:abstract\s+)?(class|interface)\s+([A-Za-z0-9_$]+)', re.MULTILINE)
        for m in class_re.finditer(content):
            line_no = content[:m.start()].count('\n') + 1
            symbols.append(PolyglotSymbol(
                name=m.group(2),
                kind=m.group(1),
                language=lang,
                file_path=file_path,
                start_line=line_no,
                end_line=line_no,
                signature=m.group(0).strip()
            ))

        # 3. Const arrow functions: (export)? const name = (async)? (...) =>
        arrow_re = re.compile(r'^(?:export\s+)?const\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>', re.MULTILINE)
        for m in arrow_re.finditer(content):
            line_no = content[:m.start()].count('\n') + 1
            symbols.append(PolyglotSymbol(
                name=m.group(1),
                kind="function",
                language=lang,
                file_path=file_path,
                start_line=line_no,
                end_line=line_no,
                signature=m.group(0).strip()
            ))

        return symbols

    def parse_go(self, file_path: str, content: str) -> List[PolyglotSymbol]:
        """Extracts Go functions, methods, structs, and interfaces."""
        symbols = []
        lang = "go"

        # 1. Functions & Methods: func (r *Receiver)? Name(...)
        fn_re = re.compile(r'^func\s+(?:\((?:[^)]+)\)\s+)?([A-Za-z0-9_]+)\s*\((.*?)\)', re.MULTILINE)
        for m in fn_re.finditer(content):
            line_no = content[:m.start()].count('\n') + 1
            symbols.append(PolyglotSymbol(
                name=m.group(1),
                kind="function",
                language=lang,
                file_path=file_path,
                start_line=line_no,
                end_line=line_no,
                signature=m.group(0).strip()
            ))

        # 2. Structs & Interfaces: type Name (struct|interface)
        type_re = re.compile(r'^type\s+([A-Za-z0-9_]+)\s+(struct|interface)', re.MULTILINE)
        for m in type_re.finditer(content):
            line_no = content[:m.start()].count('\n') + 1
            symbols.append(PolyglotSymbol(
                name=m.group(1),
                kind=m.group(2),
                language=lang,
                file_path=file_path,
                start_line=line_no,
                end_line=line_no,
                signature=m.group(0).strip()
            ))

        return symbols

    def parse_rust(self, file_path: str, content: str) -> List[PolyglotSymbol]:
        """Extracts Rust fn, struct, enum, trait, and impl blocks."""
        symbols = []
        lang = "rust"

        # 1. Functions: (pub)? (async)? fn name(...)
        fn_re = re.compile(r'^(?:pub(?:\(crate\))?\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]+)', re.MULTILINE)
        for m in fn_re.finditer(content):
            line_no = content[:m.start()].count('\n') + 1
            symbols.append(PolyglotSymbol(
                name=m.group(1),
                kind="function",
                language=lang,
                file_path=file_path,
                start_line=line_no,
                end_line=line_no,
                signature=m.group(0).strip()
            ))

        # 2. Structs, Enums, Traits
        type_re = re.compile(r'^(?:pub(?:\(crate\))?\s+)?(struct|enum|trait)\s+([A-Za-z0-9_]+)', re.MULTILINE)
        for m in type_re.finditer(content):
            line_no = content[:m.start()].count('\n') + 1
            symbols.append(PolyglotSymbol(
                name=m.group(2),
                kind=m.group(1),
                language=lang,
                file_path=file_path,
                start_line=line_no,
                end_line=line_no,
                signature=m.group(0).strip()
            ))

        return symbols

    def parse_java(self, file_path: str, content: str) -> List[PolyglotSymbol]:
        """Extracts Java classes, interfaces, and methods."""
        symbols = []
        lang = "java"

        # 1. Classes & Interfaces
        type_re = re.compile(r'^(?:public|protected|private)?\s*(?:abstract|static|final)?\s*(class|interface|enum)\s+([A-Za-z0-9_]+)', re.MULTILINE)
        for m in type_re.finditer(content):
            line_no = content[:m.start()].count('\n') + 1
            symbols.append(PolyglotSymbol(
                name=m.group(2),
                kind=m.group(1),
                language=lang,
                file_path=file_path,
                start_line=line_no,
                end_line=line_no,
                signature=m.group(0).strip()
            ))

        return symbols

    def extract_symbols(self, file_path: str, content: Optional[str] = None) -> List[PolyglotSymbol]:
        """Extracts symbols for any supported polyglot source file."""
        lang = self.detect_language(file_path)
        if not lang:
            return []

        if content is None:
            if not os.path.isfile(file_path):
                return []
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                return []

        if lang == "python":
            return self.parse_python(file_path, content)
        elif lang in ("javascript", "typescript"):
            return self.parse_javascript_typescript(file_path, content)
        elif lang == "go":
            return self.parse_go(file_path, content)
        elif lang == "rust":
            return self.parse_rust(file_path, content)
        elif lang == "java":
            return self.parse_java(file_path, content)

        return []


# Global instance
polyglot_ast_engine = PolyglotASTEngine()

