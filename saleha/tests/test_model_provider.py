import unittest
from unittest.mock import Mock, patch

from saleha.core.model_provider import OllamaProvider


class ModelProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = OllamaProvider(base_url="http://ollama.test")

    @patch("saleha.core.model_provider.requests.post")
    def test_generate_returns_provider_response(self, post):
        response = Mock()
        response.json.return_value = {"response": "hello"}
        post.return_value = response

        result = self.provider.generate("test-model", "Say hello")

        self.assertTrue(result.success)
        self.assertEqual(result.content, "hello")
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "http://ollama.test/api/generate")

    @patch("saleha.core.model_provider.requests.post")
    def test_generate_handles_connection_failure(self, post):
        post.side_effect = ConnectionError("Connection refused")

        result = self.provider.generate("test-model", "Say hello")

        self.assertFalse(result.success)
        self.assertIn("Ollama server not running", result.error_message)

    @patch("saleha.core.model_provider.requests.get")
    def test_is_available_reports_server_status(self, get):
        get.return_value.status_code = 200
        self.assertTrue(self.provider.is_available())

        get.return_value.status_code = 503
        self.assertFalse(self.provider.is_available())


if __name__ == "__main__":
    unittest.main()
