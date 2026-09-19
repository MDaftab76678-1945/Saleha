"""A reasoning model must still be able to answer a small-budget request.

Ollama bills a model's chain of thought against the same `num_predict` budget
as its answer, returning the reasoning in a separate `thinking` field. So a
budget sized for a direct-answering model can be spent entirely on thinking,
leaving `response` empty with `done_reason='length'`.

Measured on this box, prompt "Reply with only the number 2." at
num_predict=32 -- the budget `action_menu.py` uses for a single-integer
choice:

    qwen2.5-coder:3b -> done='stop',   answer='2'
    qwen3.5:4b       -> done='length', answer='',  107 chars of thinking

The same model answers correctly at 2048 (done='stop', 1299 chars), so this
was a budget problem, not a capability limit. Four of the eight models
installed here are reasoning models, and ~17 call sites hardcode a budget
without knowing which model they will be routed to -- so the growth belongs
in the provider, once.
"""

import unittest

from saleha.core.model_provider import (
    OllamaProvider,
    budget_for_model,
    is_reasoning_model,
)


class ReasoningModelDetectionTests(unittest.TestCase):

    def test_direct_answering_models_are_not_flagged(self) -> None:
        for model in ("qwen2.5-coder:3b", "qwen2.5-coder:7b",
                      "deepseek-coder:6.7b", "nomic-embed-text:latest"):
            with self.subTest(model=model):
                self.assertFalse(is_reasoning_model(model))

    def test_reasoning_models_are_flagged(self) -> None:
        for model in ("qwen3.5:4b", "qwen3.5:9b", "qwen3:8b", "deepseek-r1:7b"):
            with self.subTest(model=model):
                self.assertTrue(is_reasoning_model(model))

    def test_an_empty_or_missing_model_name_does_not_raise(self) -> None:
        self.assertFalse(is_reasoning_model(""))
        self.assertFalse(is_reasoning_model(None))  # type: ignore[arg-type]


class BudgetGrowthTests(unittest.TestCase):

    def test_direct_answering_budgets_are_left_exactly_as_asked(self) -> None:
        """Every prior measurement in this repo was taken on a non-reasoning
        model; none of them may shift."""
        for requested in (32, 400, 500, 900, 2048):
            with self.subTest(requested=requested):
                self.assertEqual(
                    budget_for_model("qwen2.5-coder:3b", requested), requested)

    def test_a_reasoning_model_gets_room_for_its_thinking_block(self) -> None:
        """32 tokens is the documented failure: entirely consumed by thinking."""
        self.assertGreaterEqual(budget_for_model("qwen3.5:4b", 32), 2048)

    def test_the_caller_s_answer_allowance_survives_on_top_of_the_headroom(self) -> None:
        """A caller asking for a large answer must not have it shrunk to the
        floor -- the thinking block is additional, not a replacement."""
        grown = budget_for_model("qwen3:8b", 4000)
        self.assertGreater(grown, 4000)

    def test_growth_never_shrinks_a_requested_budget(self) -> None:
        for model in ("qwen2.5-coder:3b", "qwen3.5:9b", "deepseek-r1:7b"):
            for requested in (32, 900, 2048, 8192):
                with self.subTest(model=model, requested=requested):
                    self.assertGreaterEqual(
                        budget_for_model(model, requested), requested)


class ProviderAppliesTheBudgetTests(unittest.TestCase):
    """The growth must reach the wire, not just exist as a helper."""

    @staticmethod
    def _options_sent(method: str, model: str, options: dict) -> dict:
        """Run the real method far enough to capture the options it builds,
        then abort before any network call."""
        sent = {}

        def _capture(*args, **kwargs):
            sent.update((kwargs.get("json") or {}).get("options", {}))
            raise RuntimeError("stop before network")

        import saleha.core.model_provider as mp
        provider = OllamaProvider()
        original = mp.requests.post
        mp.requests.post = _capture
        try:
            if method == "generate":
                provider.generate(model=model, prompt="x", options=options)
            else:
                provider.stream_generate(model=model, prompt="x",
                                         callback=lambda _c: None, options=options)
        except Exception:
            pass
        finally:
            mp.requests.post = original
        return sent

    def test_generate_grows_the_budget_on_the_wire(self) -> None:
        sent = self._options_sent("generate", "qwen3.5:4b", {"num_predict": 32})
        self.assertGreaterEqual(sent.get("num_predict", 0), 2048)

    def test_generate_leaves_a_direct_answering_model_untouched(self) -> None:
        sent = self._options_sent("generate", "qwen2.5-coder:3b", {"num_predict": 32})
        self.assertEqual(sent.get("num_predict"), 32)

    def test_stream_generate_keeps_defaults_a_partial_dict_does_not_set(self) -> None:
        """`options or {...}` dropped every default for a caller passing a
        partial dict -- fixed in generate() (pass 53), left standing here."""
        sent = self._options_sent("stream", "qwen2.5-coder:3b", {"temperature": 0.9})
        self.assertEqual(sent.get("temperature"), 0.9)
        self.assertEqual(sent.get("num_predict"), 2048)
        self.assertEqual(sent.get("repeat_penalty"), 1.15)

    def test_stream_generate_also_grows_a_reasoning_budget(self) -> None:
        sent = self._options_sent("stream", "qwen3:8b", {"num_predict": 32})
        self.assertGreaterEqual(sent.get("num_predict", 0), 2048)


if __name__ == "__main__":
    unittest.main()
