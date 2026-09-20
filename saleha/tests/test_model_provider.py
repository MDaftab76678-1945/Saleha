import unittest
from unittest.mock import Mock, patch

import requests

from saleha.core.model_provider import (
    OllamaProvider,
    OpenAICompatibleProvider,
    FallbackChainProvider,
    MockProvider,
)


class ModelProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = OllamaProvider(base_url="http://ollama.test")

    @patch("saleha.core.model_provider.requests.post")
    def test_caller_options_merge_over_defaults(self, post: Mock) -> None:
        # `options or {...}` let a caller passing only a temperature drop every
        # default, including num_predict -- and BaseAgent.think() passes exactly
        # {"temperature": t} whenever a profile sets one. qwen3:8b then hit
        # Ollama's small default budget inside its <think> block and returned an
        # empty body (done_reason='length').
        resp = Mock()
        resp.raise_for_status = Mock()
        resp.json.return_value = {"response": "ok", "eval_count": 3}
        post.return_value = resp

        self.provider.generate("m", "p", options={"temperature": 0.9})

        sent = post.call_args.kwargs["json"]["options"]
        self.assertEqual(sent["temperature"], 0.9, "caller value must win")
        self.assertEqual(sent["num_predict"], 2048, "default must survive")
        self.assertIn("top_p", sent)

    @patch("saleha.core.model_provider.requests.post")
    def test_http_200_with_empty_response_is_not_success(self, post: Mock) -> None:
        # An empty generation used to be reported as success=True with no
        # content, so every caller treated "the model said nothing" as a
        # completed call. Measured against a real agent run: three
        # `(empty reply)` turns burned the parse-retry budget, with no way to
        # tell an empty generation from a provider failure.
        resp = Mock()
        resp.raise_for_status = Mock()
        resp.json.return_value = {"response": "   ", "done_reason": "load",
                                  "eval_count": 0}
        post.return_value = resp

        result = self.provider.generate("test-model", "Say hello")

        self.assertFalse(result.success)
        self.assertEqual(result.content, "")
        self.assertIn("empty response", result.error_message)
        self.assertIn("generated", result.error_message)

    @patch("saleha.core.model_provider.requests.post")
    def test_disable_reasoning_sends_think_false(self, post: Mock) -> None:
        # Measured (pass 87): qwen3:8b on the pass-85/86 planted `requests`
        # bug took 140.4s for the correct patch with reasoning left on, and
        # 9.0s for the identical correct patch with think: false -- no
        # token-budget race, done_reason='stop' instead of 'length'.
        resp = Mock()
        resp.raise_for_status = Mock()
        resp.json.return_value = {"response": "ok", "eval_count": 3,
                                  "done_reason": "stop"}
        post.return_value = resp

        self.provider.generate("qwen3:8b", "p", disable_reasoning=True)

        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["think"], False)

    @patch("saleha.core.model_provider.requests.post")
    def test_disable_reasoning_does_not_grow_num_predict(self, post: Mock) -> None:
        # budget_for_model()'s headroom exists to survive a <think> block
        # that disable_reasoning already removes -- it must not stack.
        resp = Mock()
        resp.raise_for_status = Mock()
        resp.json.return_value = {"response": "ok", "eval_count": 3}
        post.return_value = resp

        self.provider.generate("qwen3:8b", "p", options={"num_predict": 64},
                               disable_reasoning=True)

        sent = post.call_args.kwargs["json"]["options"]
        self.assertEqual(sent["num_predict"], 64)

    @patch("saleha.core.model_provider.requests.post")
    def test_reasoning_left_on_by_default_still_grows_budget(self, post: Mock) -> None:
        """disable_reasoning defaults False -- no existing caller's behavior
        changes unless it opts in."""
        resp = Mock()
        resp.raise_for_status = Mock()
        resp.json.return_value = {"response": "ok", "eval_count": 3}
        post.return_value = resp

        self.provider.generate("qwen3:8b", "p", options={"num_predict": 64})

        sent = post.call_args.kwargs["json"]
        self.assertNotIn("think", sent)
        self.assertGreater(sent["options"]["num_predict"], 64)

    @patch("saleha.core.model_provider.requests.post")
    def test_generate_returns_provider_response(self, post: Mock) -> None:
        response = Mock()
        response.json.return_value = {"response": "hello"}
        post.return_value = response

        result = self.provider.generate("test-model", "Say hello")

        self.assertTrue(result.success)
        self.assertEqual(result.content, "hello")
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "http://ollama.test/api/generate")

    @patch("saleha.core.model_provider.requests.post")
    def test_generate_handles_connection_failure(self, post: Mock) -> None:
        post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        result = self.provider.generate("test-model", "Say hello")

        self.assertFalse(result.success)
        self.assertIn("not reachable", result.error_message)

    @patch("saleha.core.model_provider.requests.post")
    def test_generate_handles_timeout(self, post: Mock) -> None:
        post.side_effect = requests.exceptions.Timeout("timed out")

        result = self.provider.generate("test-model", "Say hello")

        self.assertFalse(result.success)
        self.assertIn("did not respond within", result.error_message)

    @patch("saleha.core.model_provider.requests.get")
    def test_is_available_reports_server_status(self, get: Mock) -> None:
        get.return_value.status_code = 200
        self.assertTrue(self.provider.is_available())

        get.return_value.status_code = 503
        self.assertFalse(self.provider.is_available())

    def test_mock_provider(self) -> None:
        mock_p = MockProvider("def test(): pass")
        self.assertTrue(mock_p.is_available())
        res = mock_p.generate("any-model", "prompt")
        self.assertTrue(res.success)
        self.assertEqual(res.content, "def test(): pass")

    @patch("saleha.core.model_provider.requests.post")
    def test_openai_compatible_provider(self, post: Mock) -> None:
        openai_p = OpenAICompatibleProvider(api_key="test-key")
        resp = Mock()
        resp.json.return_value = {
            "choices": [{"message": {"content": "OpenAI result"}}],
            "usage": {"total_tokens": 42},
        }
        post.return_value = resp

        res = openai_p.generate("gpt-4o", "Hello")
        self.assertTrue(res.success)
        self.assertEqual(res.content, "OpenAI result")
        self.assertEqual(res.tokens_used, 42)

    def test_fallback_chain_provider(self) -> None:
        failing_p = Mock()
        failing_p.is_available.return_value = False

        working_p = MockProvider("Fallback Success")
        chain = FallbackChainProvider([failing_p, working_p])

        self.assertTrue(chain.is_available())
        res = chain.generate("model", "prompt")
        self.assertTrue(res.success)
        self.assertEqual(res.content, "Fallback Success")

    def test_mock_provider_stream_generate_delivers_one_chunk(self) -> None:
        # MockProvider has no real streaming backend -- the base class's
        # stream_generate() degrades to one callback with the whole content,
        # which is honest (not a fabricated multi-chunk stream).
        mock_p = MockProvider("line one\nline two")
        chunks: list = []
        res = mock_p.stream_generate("any-model", "prompt", callback=chunks.append)

        self.assertTrue(res.success)
        self.assertEqual(chunks, ["line one\nline two"])
        self.assertEqual(res.content, "line one\nline two")

    @patch("saleha.core.model_provider.requests.post")
    def test_ollama_stream_generate_yields_multiple_chunks(self, post: Mock) -> None:
        # Ollama's stream:true response is newline-delimited JSON, one object
        # per chunk, with a final done:true object carrying eval_count.
        lines = [
            '{"response": "Hel", "done": false}',
            '{"response": "lo", "done": false}',
            '{"response": "", "done": true, "eval_count": 7}',
        ]
        response = Mock()
        response.iter_lines.return_value = lines
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        post.return_value = response

        chunks: list = []
        res = self.provider.stream_generate("test-model", "Say hello", callback=chunks.append)

        self.assertTrue(res.success)
        self.assertEqual(chunks, ["Hel", "lo"])
        self.assertEqual(res.content, "Hello")
        self.assertEqual(res.tokens_used, 7)
        self.assertEqual(post.call_args.kwargs["json"]["stream"], True)

    @patch("saleha.core.model_provider.requests.post")
    def test_ollama_stream_generate_handles_connection_failure(self, post: Mock) -> None:
        post.side_effect = requests.exceptions.ConnectionError("refused")

        chunks: list = []
        res = self.provider.stream_generate("test-model", "Say hello", callback=chunks.append)

        self.assertFalse(res.success)
        self.assertEqual(chunks, [])
        self.assertIn("not reachable", res.error_message)


if __name__ == "__main__":
    unittest.main()
