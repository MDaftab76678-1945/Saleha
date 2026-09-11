import unittest
from unittest.mock import patch

from saleha.core.model_provider import MockProvider
from saleha.core.streaming_ui import StreamRenderer


class StreamingUiTests(unittest.TestCase):
    def test_stream_to_terminal_returns_generated_content(self) -> None:
        # Regression test: stream_to_terminal previously called
        # default_provider.stream_generate(), a method that did not exist on
        # any provider -- every real invocation raised AttributeError. This
        # exercises the real code path (Rich Live rendering included) against
        # a provider that now genuinely implements stream_generate.
        mock_provider = MockProvider("def add(a, b):\n    return a + b")
        with patch("saleha.core.streaming_ui.default_provider", mock_provider):
            renderer = StreamRenderer()
            result = renderer.stream_to_terminal(model="mock", prompt="write add()")

        self.assertEqual(result, "def add(a, b):\n    return a + b")

    def test_stream_to_terminal_reports_provider_failure(self) -> None:
        class FailingProvider(MockProvider):
            def stream_generate(self, model, prompt, callback, options=None):
                from saleha.core.model_provider import ProviderResponse
                return ProviderResponse(success=False, content="", error_message="offline")

        with patch("saleha.core.streaming_ui.default_provider", FailingProvider()):
            renderer = StreamRenderer()
            result = renderer.stream_to_terminal(model="mock", prompt="write add()")

        # No exception, and no fabricated content on a failed stream.
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
