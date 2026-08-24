"""BOM strip: PowerShell UTF8 edits ne BOM laga diya tha jo pip/TOML ko todta hai."""
import os

targets = [
    "pyproject.toml",
    "setup.py",
    "saleha/__init__.py",
    "vscode-extension/package.json",
]

for path in targets:
    with open(path, "rb") as f:
        raw = f.read()
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    status = "BOM FOUND -> stripped" if had_bom else "clean"
    if had_bom:
        with open(path, "wb") as f:
            f.write(raw[3:])
    print(f"{path}: {status}")
