"""Unit tests for Floating Desktop Sidecar Daemon & Micro-Server."""

import unittest
from unittest.mock import patch

from saleha.agents.coder import CoderAgent
from saleha.core.platform.model_provider import MockProvider
from saleha.core.sidecar_daemon import SIDECAR_HTML, SidecarHandler


class SidecarDaemonTests(unittest.TestCase):

    def test_sidecar_html_content(self) -> None:
        self.assertIn("Saleha Desktop Sidecar", SIDECAR_HTML)
        self.assertIn("runAction('explain')", SIDECAR_HTML)
        self.assertIn("runAction('sast')", SIDECAR_HTML)

    def test_fix_empty_code_does_not_call_model(self) -> None:
        self.assertEqual(SidecarHandler._run_fix(""), "No code provided.")

    def test_test_empty_code_does_not_call_model(self) -> None:
        self.assertEqual(SidecarHandler._run_test(""), "No code provided.")

    def test_explain_empty_code_does_not_call_model(self) -> None:
        self.assertEqual(SidecarHandler._run_explain(""), "No code provided.")

    @staticmethod
    def _coder_with_mock(response_text: str) -> CoderAgent:
        coder = CoderAgent()
        coder.provider = MockProvider(default_response=response_text)
        return coder

    def test_fix_uses_real_model_call_not_hardcoded_text(self) -> None:
        # Regression guard: the old implementation returned the caller's
        # unmodified input plus a hardcoded "Handled edge cases safely"
        # comment, for any input. A real repair call goes through the model
        # provider chain -- with a mock provider returning a fixed but
        # DIFFERENT body, the output must reflect that body, not the input.
        mock_coder = self._coder_with_mock("def fixed():\n    return 1")
        with patch("saleha.agents.coder.CoderAgent", return_value=mock_coder):
            result = SidecarHandler._run_fix("def broken():\n    return None  # bug")
        self.assertIn("def fixed():", result)
        self.assertNotIn("Handled edge cases safely", result)
        self.assertNotIn("def broken():", result)

    def test_test_uses_real_model_call_not_hardcoded_stub(self) -> None:
        mock_coder = self._coder_with_mock("def test_real():\n    assert 1 == 1")
        with patch("saleha.agents.coder.CoderAgent", return_value=mock_coder):
            result = SidecarHandler._run_test("def add(a, b):\n    return a + b")
        self.assertIn("def test_real():", result)
        self.assertNotIn("class TestGenerated", result)
        self.assertNotIn("assertTrue(True)", result)

    def test_test_reports_honest_failure_when_model_produces_no_test(self) -> None:
        # MockProvider's own default body ("def solve(): return 42") has no
        # test function in it, so generate_tests's has_test check correctly
        # rejects it -- the sidecar must surface that as a real failure, not
        # a fabricated stub.
        mock_coder = self._coder_with_mock("def solve():\n    return 42")
        with patch("saleha.agents.coder.CoderAgent", return_value=mock_coder):
            result = SidecarHandler._run_test("def add(a, b):\n    return a + b")
        self.assertIn("failed", result.lower())
        self.assertNotIn("assertTrue(True)", result)

    def test_explain_reflects_real_input_not_a_fixed_string(self) -> None:
        # Regression guard: the old implementation always returned "Code
        # defines standard execution logic with clean structure" for any
        # input. This is real AST analysis, so different inputs must
        # produce different output.
        simple = SidecarHandler._run_explain("x = 1")
        complex_code = (
            "def f(a, b):\n"
            "    try:\n"
            "        return a / b\n"
            "    except ZeroDivisionError:\n"
            "        return None\n"
        )
        complex_result = SidecarHandler._run_explain(complex_code)
        self.assertNotEqual(simple, complex_result)
        self.assertNotIn("Code defines standard execution logic with clean structure", simple)


if __name__ == "__main__":
    unittest.main()

