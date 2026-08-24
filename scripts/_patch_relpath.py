"""One-shot: replace os.path.relpath with safe_relpath across call-sites."""
import io
import re

files = {
    "saleha/agentic_loop.py": "saleha/core/agentic_loop.py",
    "saleha/autodoc_generator.py": "saleha/core/autodoc_generator.py",
    "saleha/codebase_indexer.py": "saleha/core/codebase_indexer.py",
    "saleha/dependency_graph.py": "saleha/core/dependency_graph.py",
    "saleha/polyglot_indexer.py": "saleha/core/polyglot_indexer.py",
    "saleha/repo_context_packer.py": "saleha/core/repo_context_packer.py",
    "saleha/security_scanner.py": "saleha/core/security_scanner.py",
}

IMPORT_LINE = "from saleha.core.path_utils import safe_relpath\n"

for display, path in files.items():
    src = io.open(path, encoding="utf-8").read()
    if "safe_relpath" in src:
        print(f"skip (already patched): {display}")
        continue
    count = src.count("os.path.relpath(")
    src = src.replace("os.path.relpath(", "safe_relpath(")
    # import ko pehle 'import' block ke baad jodo: last top-level import ke baad
    lines = src.splitlines(keepends=True)
    last_import = max(i for i, l in enumerate(lines) if l.startswith(("import ", "from ")))
    lines.insert(last_import + 1, IMPORT_LINE)
    io.open(path, "w", encoding="utf-8", newline="").write("".join(lines))
    print(f"{display}: {count} call(s) swapped")
