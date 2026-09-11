"""Unit tests for saleha.core.path_utils. Had no test coverage before this
file (found during a test-coverage sweep of saleha/core/)."""

import os
import unittest

from saleha.core.path_utils import safe_relpath, posix_basename


class SafeRelpathTests(unittest.TestCase):
    def test_normal_case_matches_os_path_relpath(self) -> None:
        start = os.path.join("C:" if os.name == "nt" else "/", "a")
        path = os.path.join(start, "b", "c.py")
        self.assertEqual(safe_relpath(path, start), os.path.relpath(path, start))

    def test_cross_drive_falls_back_to_absolute_path(self) -> None:
        if os.name != "nt":
            self.skipTest("cross-drive ValueError is a Windows-only os.path.relpath behavior")
        # D:\ vs C:\ raises ValueError from os.path.relpath on Windows.
        result = safe_relpath(r"D:\project\file.py", r"C:\other")
        self.assertEqual(result, os.path.abspath(r"D:\project\file.py"))


class PosixBasenameTests(unittest.TestCase):
    def test_forward_slash_path(self) -> None:
        self.assertEqual(posix_basename("a/b/c.py"), "c.py")

    def test_backslash_path(self) -> None:
        self.assertEqual(posix_basename("a\\b\\c.py"), "c.py")

    def test_mixed_separators(self) -> None:
        self.assertEqual(posix_basename("a/b\\c/d.py"), "d.py")

    def test_no_separator_returns_whole_string(self) -> None:
        self.assertEqual(posix_basename("solo.py"), "solo.py")


if __name__ == "__main__":
    unittest.main()
