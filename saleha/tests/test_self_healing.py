"""
Unit tests for SelfHealingEngine and Error Reflexion.
Validates error classification, traceback frame parsing, defect localization, and import auto-patching.
"""

from __future__ import annotations

import unittest

from saleha.core.self_healing import SelfHealingEngine


class SelfHealingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = SelfHealingEngine()

    def test_classifies_syntax_error(self) -> None:
        result = self.engine.analyze_and_heal(
            "SyntaxError: invalid syntax", "Create a function"
        )
        self.assertTrue(result.error_detected)
        self.assertEqual(result.error_type, "SyntaxError")
        self.assertIn("Root Cause Hint", result.reflexion_prompt)
        self.assertIn("Create a function", result.reflexion_prompt)

    def test_classifies_import_error(self) -> None:
        result = self.engine.analyze_and_heal(
            "ModuleNotFoundError: No module named 'pandas'", "Read a CSV"
        )
        self.assertEqual(result.error_type, "ImportError")
        self.assertIn("library", result.root_cause_hint)
        self.assertTrue(result.root_cause_hint.isascii())

    def test_known_error_type_is_reported_detected(self) -> None:
        result = self.engine.analyze_and_heal("RuntimeError: failed", "Run task")
        self.assertTrue(result.error_detected)
        self.assertEqual(result.error_type, "RuntimeError")
        self.assertTrue(result.reflexion_prompt)

    def test_truly_unknown_error_is_honestly_undetected(self) -> None:
        result = self.engine.analyze_and_heal(
            "FrobnicationFault: the widget could not be frobnicated", "Run task"
        )
        self.assertFalse(result.error_detected)
        self.assertEqual(result.error_type, "UnknownError")
        self.assertTrue(result.reflexion_prompt)

    def test_empty_error_log_is_a_noop(self) -> None:
        result = self.engine.analyze_and_heal("", "No error")
        self.assertFalse(result.error_detected)
        self.assertEqual(result.error_type, "None")
        self.assertEqual(result.reflexion_prompt, "")

    def test_auto_patch_missing_imports(self) -> None:
        code = "def delay():\n    time.sleep(1)\n    return json.dumps({'ok': True})"
        patched = self.engine.auto_patch_code(code)
        self.assertIn("import time", patched)
        self.assertIn("import json", patched)

    def test_auto_patch_java_hallucinations(self) -> None:
        code = "class Counter:\n    def __init__(self):\n        self.val = AtomicInteger(10)\n        System.out.println('init')"
        patched = self.engine.auto_patch_code(code)
        self.assertNotIn("AtomicInteger", patched)
        self.assertNotIn("System.out.println", patched)
        self.assertIn("print('init')", patched)

    def test_extract_traceback_frames(self) -> None:
        tb = """
Traceback (most recent call last):
  File "saleha/core/math_logic.py", line 42, in compute_ratio
    return a / b
ZeroDivisionError: division by zero
"""
        frames = self.engine.extract_traceback_frames(tb)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["file"], "saleha/core/math_logic.py")
        self.assertEqual(frames[0]["line"], 42)
        self.assertEqual(frames[0]["symbol"], "compute_ratio")
        self.assertEqual(frames[0]["code_line"], "return a / b")

    def test_traceback_localization_in_healing_result(self) -> None:
        tb = """
Traceback (most recent call last):
  File "app/service.py", line 105, in run_service
    res = helper()
NameError: name 'helper' is not defined
"""
        result = self.engine.analyze_and_heal(tb, "Execute service pipeline")
        self.assertTrue(result.error_detected)
        self.assertEqual(result.error_type, "NameError")
        self.assertEqual(result.faulting_file, "app/service.py")
        self.assertEqual(result.faulting_line, 105)
        self.assertEqual(result.faulting_symbol, "run_service")
        self.assertIn("Faulting Location: app/service.py:105 (in run_service)", result.reflexion_prompt)
        self.assertIn("Failing Code: res = helper()", result.reflexion_prompt)

    def test_auto_patch_typing_and_pathlib(self) -> None:
        code = "def process(items: List[str], mapping: Dict[str, Any]) -> Optional[Path]:\n    return Path('/tmp')"
        patched = self.engine.auto_patch_code(code)
        self.assertIn("from typing import", patched)
        self.assertIn("List", patched)
        self.assertIn("Dict", patched)
        self.assertIn("Optional", patched)
        self.assertIn("from pathlib import Path", patched)


if __name__ == "__main__":
    unittest.main()
