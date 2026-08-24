import unittest
from unittest.mock import patch, MagicMock
from saleha.core.hybrid_gateway import HybridModelGateway, GatewayResponse


class HybridGatewayTests(unittest.TestCase):
    def setUp(self):
        self.gateway = HybridModelGateway()

    def test_list_providers(self):
        providers = self.gateway.list_available_providers()
        self.assertIn("ollama", providers)
        self.assertIn("groq", providers)
        self.assertIn("openai", providers)
        self.assertIn("anthropic", providers)

    def test_ollama_call_mock(self):
        with patch.object(self.gateway, "_call_ollama") as mock_ollama:
            mock_ollama.return_value = GatewayResponse(
                content="def hello(): return 'world'",
                provider="ollama",
                model="deepseek-coder:6.7b",
                latency=0.1,
                success=True
            )
            res = self.gateway.generate("write hello function", provider="ollama")
            self.assertTrue(res.success)
            self.assertEqual(res.provider, "ollama")
            self.assertIn("hello", res.content)

    def test_groq_api_call_mock(self):
        with patch.object(self.gateway, "_call_openai_compatible") as mock_groq:
            mock_groq.return_value = GatewayResponse(
                content="Fast Groq Llama-3 response",
                provider="groq",
                model="llama-3.3-70b-versatile",
                latency=0.05,
                success=True,
                tokens_used=42
            )
            res = self.gateway.generate("Test prompt", provider="groq")
            self.assertTrue(res.success)
            self.assertEqual(res.tokens_used, 42)
            self.assertEqual(res.provider, "groq")


if __name__ == "__main__":
    unittest.main()

