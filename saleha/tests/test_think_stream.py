"""A2: Token-level streaming (think_stream) tests."""
import unittest
from unittest.mock import patch, MagicMock

from saleha.agents.base_agent import BaseAgent, AgentResponse
from saleha.core.model_provider import ProviderResponse


class _StreamProvider:
    """Records calls; emits tokens via callback like OllamaProvider.stream_generate."""

    def __init__(self, tokens=("hel", "lo ", "world")):
        self.tokens = tokens
        self.calls = []

    def stream_generate(self, model, prompt, callback=None, options=None):
        self.calls.append(model)
        for t in self.tokens:
            if callback:
                callback(t)
        return ProviderResponse(success=True, content="".join(self.tokens), response_time=0.05)

    def generate(self, model, prompt, options=None):
        raise AssertionError("generate() must NOT be called when streaming is supported")


class _NoStreamProvider:
    def generate(self, model, prompt, options=None):
        return ProviderResponse(success=True, content="plain", response_time=0.01)


class ThinkStreamTests(unittest.TestCase):
    def test_tokens_fire_and_full_response_returned(self):
        agent = BaseAgent(role="T", model="fixed-model", provider=_StreamProvider())
        seen = []
        resp = agent.think_stream("hi", on_token=seen.append)

        self.assertEqual("".join(seen), "hello world")
        self.assertTrue(resp.success)
        self.assertEqual(resp.content, "hello world")
        self.assertEqual(resp.model_used, "fixed-model")

    def test_fallback_when_provider_has_no_stream(self):
        agent = BaseAgent(role="T", model="fixed-model", provider=_NoStreamProvider())
        seen = []
        resp = agent.think_stream("hi", on_token=seen.append)

        self.assertEqual(seen, [])  # koi token nahi
        self.assertTrue(resp.success)
        self.assertEqual(resp.content, "plain")

    def test_router_stats_recorded_on_stream_path(self):
        provider = _StreamProvider()
        agent = BaseAgent(role="T", model="auto", provider=provider)
        with patch.object(agent.router, "select_model", return_value="qwen3:4b") as sel, \
             patch.object(agent.router, "record_result") as rec:
            agent.think_stream("hello task")
        sel.assert_called_once()
        rec.assert_called_once()
        args = rec.call_args[0]
        self.assertEqual(args[2], "qwen3:4b")  # model_used
        self.assertTrue(args[3] >= 0)          # response_time
        self.assertTrue(args[4])               # success

    def test_reflexion_appended_in_stream_prompt(self):
        provider = _StreamProvider()
        captured = {}

        def spy_stream(model, prompt, callback=None, options=None):
            captured["prompt"] = prompt
            return ProviderResponse(success=True, content="ok", response_time=0.01)

        provider.stream_generate = spy_stream
        agent = BaseAgent(role="T", model="m", provider=provider)
        agent.think_stream("fix it", previous_error_reflexion="SELF HEAL HINT")
        self.assertIn("SELF HEAL HINT", captured["prompt"])


if __name__ == "__main__":
    unittest.main()
