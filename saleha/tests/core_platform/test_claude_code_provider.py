"""ClaudeCodeProvider: Claude via `claude -p`, routing, and the local-only switch."""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from typing import Any, List
from unittest.mock import patch

from saleha.core.platform.context_budget import context_window_for
from saleha.core.platform.model_provider import (
    ClaudeCodeProvider,
    FallbackChainProvider,
    GeminiProvider,
    OllamaProvider,
    ProviderResponse,
)


def _completed(stdout: str, code: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr="")


class ClaudeCodeProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = ClaudeCodeProvider(executable="claude")
        self.calls: List[Any] = []

    def _fake_run(self, stdout: str, code: int = 0) -> Any:
        def run(argv: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
            self.calls.append((argv, kwargs))
            return _completed(stdout, code)
        return run

    def test_parses_result_cost_and_passes_prompt_on_stdin(self) -> None:
        out = json.dumps({"result": "2", "is_error": False, "total_cost_usd": 0.02,
                          "usage": {"input_tokens": 5, "output_tokens": 1}})
        with patch.dict(os.environ, {"SALEHA_LOCAL_ONLY": ""}), \
                patch("subprocess.run", self._fake_run(out)):
            res = self.provider.generate("claude-code:sonnet", "Reply with 2")
        self.assertTrue(res.success)
        self.assertEqual(res.content, "2")
        self.assertEqual(res.cost_usd, 0.02)
        argv, kwargs = self.calls[0]
        self.assertEqual(kwargs["input"], "Reply with 2")
        self.assertEqual(argv[argv.index("--model") + 1], "sonnet")
        self.assertEqual(argv[argv.index("--tools") + 1], "")   # no tools: text only

    def test_error_result_is_a_failure_not_an_answer(self) -> None:
        out = json.dumps({"result": "Credit balance too low", "is_error": True})
        with patch.dict(os.environ, {"SALEHA_LOCAL_ONLY": ""}), \
                patch("subprocess.run", self._fake_run(out, code=1)):
            res = self.provider.generate("claude-code", "hi")
        self.assertFalse(res.success)
        self.assertEqual(res.content, "")
        self.assertIn("Credit balance", res.error_message)

    def test_local_only_refuses_without_running_anything(self) -> None:
        with patch.dict(os.environ, {"SALEHA_LOCAL_ONLY": "1"}), \
                patch("subprocess.run", self._fake_run("{}")):
            res = self.provider.generate("claude-code:sonnet", "secret code")
        self.assertFalse(res.success)
        self.assertIn("SALEHA_LOCAL_ONLY", res.error_message)
        self.assertEqual(self.calls, [])

    def test_missing_cli_is_reported(self) -> None:
        res = ClaudeCodeProvider(executable="").generate("claude-code", "hi")
        self.assertFalse(res.success)
        self.assertIn("not found", res.error_message)


class RoutingTests(unittest.TestCase):
    def test_claude_code_model_skips_the_local_chain(self) -> None:
        chain = FallbackChainProvider(providers=[OllamaProvider()])
        answer = ProviderResponse(True, "ok", provider_name="claude_code")
        with patch.object(ClaudeCodeProvider, "generate", return_value=answer) as cloud, \
                patch.object(OllamaProvider, "generate") as local:
            res = chain.generate("claude-code:haiku", "hi")
        self.assertEqual(res.provider_name, "claude_code")
        cloud.assert_called_once()
        local.assert_not_called()

    def test_claude_prompts_are_not_trimmed_to_the_8k_default(self) -> None:
        self.assertEqual(context_window_for("claude-code:sonnet"), 200000)


class _Resp:
    def __init__(self, status: int, data: Any) -> None:
        self.status_code = status
        self._data = data

    def json(self) -> Any:
        return self._data


class GeminiProviderTests(unittest.TestCase):
    def test_parses_text_and_sends_key_only_in_a_header(self) -> None:
        seen: List[Any] = []

        def post(url: str, **kwargs: Any) -> _Resp:
            seen.append((url, kwargs))
            return _Resp(200, {"candidates": [{"content": {"parts": [{"text": "4"}]}}],
                               "usageMetadata": {"totalTokenCount": 7}})

        with patch.dict(os.environ, {"SALEHA_LOCAL_ONLY": ""}), \
                patch("saleha.core.platform.model_provider.requests.post", post):
            res = GeminiProvider(api_key="SECRET-KEY").generate("gemini:gemini-3.5-flash", "2+2?")
        self.assertTrue(res.success)
        self.assertEqual(res.content, "4")
        url, kwargs = seen[0]
        self.assertIn("gemini-3.5-flash:generateContent", url)
        self.assertNotIn("SECRET-KEY", url)
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "SECRET-KEY")

    def test_http_error_is_a_failure_with_the_reason(self) -> None:
        with patch.dict(os.environ, {"SALEHA_LOCAL_ONLY": ""}), \
                patch("saleha.core.platform.model_provider.time.sleep"), \
                patch("saleha.core.platform.model_provider.requests.post",
                      lambda url, **kw: _Resp(429, {"error": {"message": "quota exceeded"}})):
            res = GeminiProvider(api_key="k").generate("gemini", "hi")
        self.assertFalse(res.success)
        self.assertIn("429", res.error_message)
        self.assertIn("quota", res.error_message)

    def test_transient_503_is_retried(self) -> None:
        replies = [_Resp(503, {"error": {"message": "high demand"}}),
                   _Resp(200, {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})]
        with patch.dict(os.environ, {"SALEHA_LOCAL_ONLY": ""}), \
                patch("saleha.core.platform.model_provider.time.sleep") as slept, \
                patch("saleha.core.platform.model_provider.requests.post",
                      lambda url, **kw: replies.pop(0)):
            res = GeminiProvider(api_key="k").generate("gemini", "hi")
        self.assertTrue(res.success, res.error_message)
        slept.assert_called_once()

    def test_blocked_or_empty_answer_is_not_success(self) -> None:
        with patch.dict(os.environ, {"SALEHA_LOCAL_ONLY": ""}), \
                patch("saleha.core.platform.model_provider.requests.post",
                      lambda url, **kw: _Resp(200, {"promptFeedback": {"blockReason": "SAFETY"}})):
            res = GeminiProvider(api_key="k").generate("gemini", "hi")
        self.assertFalse(res.success)
        self.assertIn("SAFETY", res.error_message)

    def test_missing_key_and_local_only_refuse(self) -> None:
        self.assertIn("GEMINI_API_KEY", GeminiProvider(api_key="").generate("gemini", "x").error_message)
        with patch.dict(os.environ, {"SALEHA_LOCAL_ONLY": "1"}):
            self.assertIn("SALEHA_LOCAL_ONLY",
                          GeminiProvider(api_key="k").generate("gemini", "x").error_message)

    def test_model_names_and_windows(self) -> None:
        self.assertEqual(GeminiProvider.api_model("gemini:gemini-2.5-pro"), "gemini-2.5-pro")
        self.assertEqual(GeminiProvider.api_model("gemini-2.5-pro"), "gemini-2.5-pro")
        self.assertEqual(context_window_for("gemini-2.5-pro"), 1000000)
        self.assertEqual(context_window_for("gemma4:31b-cloud"), 8192)


if __name__ == "__main__":
    unittest.main()
