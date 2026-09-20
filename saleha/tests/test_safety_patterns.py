from __future__ import annotations

import unittest
from typing import List

from saleha.core.safety_patterns import (
    BLOCKED_IMPORTS,
    DangerPattern,
    check_all_dangerous,
    check_dangerous,
    get_blocked_import_list,
)


class SafetyPatternsTests(unittest.TestCase):
    def test_eval_detected(self) -> None:
        code = "result = eval('2 + 2')"
        match = check_dangerous(code)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn("eval()", match.description)

    def test_exec_detected(self) -> None:
        code = "exec('import sys')"
        match = check_dangerous(code)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn("exec()", match.description)

    def test_os_system_detected(self) -> None:
        code = "os.system('ls -la')"
        match = check_dangerous(code)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn("os.system", match.description)

    def test_subprocess_call_detected(self) -> None:
        code = "subprocess.call(['whoami'])"
        match = check_dangerous(code)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn("subprocess.call", match.description)

    def test_shutil_rmtree_root_detected(self) -> None:
        code = "shutil.rmtree('/etc')"
        match = check_dangerous(code)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn("shutil.rmtree", match.description)

    def test_rm_rf_shell_detected(self) -> None:
        code = "os.system('rm -rf /')"
        all_matches = check_all_dangerous(code)
        descriptions = [m.description for m in all_matches]
        self.assertTrue(any("rm -rf" in d for d in descriptions))

    def test_blocked_static_import(self) -> None:
        code = "import socket\ns = socket.socket()"
        match = check_dangerous(code)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.pattern, "[import-check]")
        self.assertIn("socket", match.description)

    def test_blocked_static_import_from(self) -> None:
        code = "from subprocess import Popen"
        match = check_dangerous(code)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.pattern, "[import-check]")
        self.assertIn("subprocess", match.description)

    def test_blocked_dynamic_import_dunder(self) -> None:
        code = 'mod = __import__("socket")'
        match = check_dangerous(code)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn('__import__("socket")', match.description)

    def test_blocked_dynamic_import_importlib(self) -> None:
        code = 'mod = importlib.import_module("os")'
        match = check_dangerous(code)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn('importlib.import_module("os")', match.description)

    def test_blocked_dynamic_import_importlib_keyword_arg(self) -> None:
        code = 'mod = importlib.import_module(name="subprocess")'
        match = check_dangerous(code)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn('importlib.import_module("subprocess")', match.description)

    def test_safe_pure_code(self) -> None:
        code = """
def compute_sum(values: list[int]) -> int:
    return sum(values)

result = compute_sum([1, 2, 3, 4])
"""
        match = check_dangerous(code)
        self.assertIsNone(match)

    def test_safe_standard_imports(self) -> None:
        code = """
import math
import json
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Point:
    x: float
    y: float

p = Point(3.0, 4.0)
dist = math.sqrt(p.x**2 + p.y**2)
"""
        match = check_dangerous(code)
        self.assertIsNone(match)

    def test_get_blocked_import_list(self) -> None:
        blocked = get_blocked_import_list()
        self.assertIsInstance(blocked, list)
        self.assertTrue(len(blocked) >= len(BLOCKED_IMPORTS))
        self.assertEqual(blocked, sorted(list(BLOCKED_IMPORTS)))
        self.assertIn("os", blocked)
        self.assertIn("subprocess", blocked)
        self.assertIn("socket", blocked)
        self.assertIn("importlib", blocked)

    def test_check_all_dangerous(self) -> None:
        code = """
import socket
import os
os.system("echo compromised")
eval("1 + 1")
"""
        findings: List[DangerPattern] = check_all_dangerous(code)
        self.assertTrue(len(findings) >= 3)
        descriptions = [f.description for f in findings]
        self.assertTrue(any("os.system" in d for d in descriptions))
        self.assertTrue(any("eval()" in d for d in descriptions))
        self.assertTrue(any("[import-check]" == f.pattern for f in findings))

    def test_syntax_error_handled_gracefully(self) -> None:
        broken_code = "def incomplete_func(:"
        match = check_dangerous(broken_code)
        self.assertIsNone(match)


if __name__ == "__main__":
    unittest.main()
