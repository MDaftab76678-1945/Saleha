"""
Saleha Core: Cross-platform Path Helpers

Windows par os.path.relpath() cross-drive paths (C: vs D:) pe ValueError
throw karta hai -- CI runners pe checkout alag drive pe hota hai aur
yehi chupke se test suites toda tha. safe_relpath() un cases me absolute
path fallback deta hai.
"""

import os


def safe_relpath(path: str, start: str) -> str:
    """os.path.relpath lekin cross-drive ValueError pe abs-path fallback."""
    try:
        return os.path.relpath(path, start)
    except ValueError:
        # Alag drive/mount -- relative impossible; absolute hi sahi
        return os.path.abspath(path)


def posix_basename(path: str) -> str:
    """Backslash-forwardslash dono handle karne wala basename."""
    return path.replace("\\", "/").rsplit("/", 1)[-1]
