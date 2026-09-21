"""
Saleha Core: Cross-platform Path Helpers

On Windows, os.path.relpath() raises ValueError for cross-drive paths
(C: vs D:) -- CI runners with a checkout on a different drive hit this
silently and it broke test suites. safe_relpath() falls back to an
absolute path in that case.
"""

import os


def safe_relpath(path: str, start: str) -> str:
    """os.path.relpath, falling back to an absolute path on a cross-drive ValueError."""
    try:
        return os.path.relpath(path, start)
    except ValueError:
        # Different drive/mount -- a relative path is impossible; absolute is correct.
        return os.path.abspath(path)


def posix_basename(path: str) -> str:
    """basename that handles both backslash and forward-slash separators."""
    return path.replace("\\", "/").rsplit("/", 1)[-1]
