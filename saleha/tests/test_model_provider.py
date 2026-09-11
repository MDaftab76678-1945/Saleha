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
