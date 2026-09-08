import unittest

from saleha.core.self_healing import SelfHealingEngine


class SelfHealingEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = SelfHealingEngine()

    def test_classifies_syntax_error(self):
        result = self.engine.analyze_and_heal(
            "SyntaxError: invalid syntax", "Create a function"
        )

        self.assertTrue(result.error_detected)
        self.assertEqual(result.error_type, "SyntaxError")
        self.assertIn("Root Cause Hint", result.reflexion_prompt)
        self.assertIn("Create a function", result.reflexion_prompt)

    def test_classifies_import_error(self):
        result = self.engine.analyze_and_heal(
            "ModuleNotFoundError: No module named 'pandas'", "Read a CSV"
        )

        self.assertEqual(result.error_type, "ImportError")
        self.assertIn("लाइब्रेरी", result.root_cause_hint)

    def test_known_error_type_is_reported_detected(self):
        # RuntimeError used to be absent from ERROR_PATTERNS -- this exact
        # input was the "unknown error" case. It is now a known pattern
        # (pass 30), so this asserts the classified-and-detected path
        # instead; test_truly_unknown_error_is_honestly_undetected below
        # covers the actual "cannot classify" case that this test's old name
        # claimed to.
        result = self.engine.analyze_and_heal("RuntimeError: failed", "Run task")

        self.assertTrue(result.error_detected)
        self.assertEqual(result.error_type, "RuntimeError")
        self.assertTrue(result.reflexion_prompt)

    def test_truly_unknown_error_is_honestly_undetected(self):
        # error_detected used to be hardcoded True unconditionally (except
        # for an empty log) -- so a log matching no known pattern still
        # reported error_detected=True, alongside error_type="UnknownError".
        # That is a contradiction: "detected" and "unknown" cannot both be
        # true. Guidance is still generated (self-healing should not refuse
        # to try just because it cannot name the error), but error_detected
        # must honestly say classification failed.
        result = self.engine.analyze_and_heal(
            "FrobnicationFault: the widget could not be frobnicated", "Run task"
        )

        self.assertFalse(result.error_detected)
        self.assertEqual(result.error_type, "UnknownError")
        self.assertTrue(result.reflexion_prompt)

    def test_empty_error_log_is_a_noop(self):
        result = self.engine.analyze_and_heal("", "No error")

        self.assertFalse(result.error_detected)
        self.assertEqual(result.error_type, "None")
        self.assertEqual(result.reflexion_prompt, "")

    def test_auto_patch_missing_imports(self):
        code = "def delay():\n    time.sleep(1)\n    return json.dumps({'ok': True})"
        patched = self.engine.auto_patch_code(code)
        self.assertIn("import time", patched)
        self.assertIn("import json", patched)

    def test_auto_patch_java_hallucinations(self):
        code = "class Counter:\n    def __init__(self):\n        self.val = AtomicInteger(10)\n        System.out.println('init')"
        patched = self.engine.auto_patch_code(code)
        self.assertNotIn("AtomicInteger", patched)
        self.assertNotIn("System.out.println", patched)
        self.assertIn("print('init')", patched)


if __name__ == "__main__":
    unittest.main()
