"""
Tests for the context budget guard.

The failure this guards against, measured on this box against
qwen2.5-coder:3b (32768-token window):

    prompt   54 KB  -> answer recalled correctly
    prompt  280 KB  -> success=True, answer LOST  ("Magic is the magic word.")
    prompt  840 KB  -> success=True, answer LOST  ('The magic word is "yes".')

The magic word sat at the START of the prompt, the question at the END. Past
the window Ollama drops the middle silently: no error, no warning, and a
confident wrong answer that nothing downstream can distinguish from a real one.

After the guard, the same 280 KB prompt recalls the answer correctly.

No model is contacted here: the budget arithmetic is pure.
"""

from __future__ import annotations

import unittest

from saleha.core.context_budget import (
    DEFAULT_CONTEXT_WINDOW,
    BudgetCheck,
    check,
    context_window_for,
    estimate_tokens,
    fit,
    fit_code_block,
    token_budget,
)

MODEL = "qwen2.5-coder:3b"


class ContextWindowLookupTests(unittest.TestCase):
    def test_known_model_exact(self):
        self.assertEqual(context_window_for(MODEL), 32768)

    def test_family_prefix_match(self):
        """A tag this table has not seen should still match its family."""
        self.assertEqual(context_window_for("qwen2.5-coder:14b"), 32768)

    def test_unknown_model_is_conservative_not_optimistic(self):
        """Guessing high here means silent truncation -- the whole failure."""
        self.assertEqual(context_window_for("brand-new-model:70b"),
                         DEFAULT_CONTEXT_WINDOW)

    def test_empty_and_none_are_safe(self):
        self.assertEqual(context_window_for(""), DEFAULT_CONTEXT_WINDOW)
        self.assertEqual(context_window_for(None), DEFAULT_CONTEXT_WINDOW)


class EstimateTests(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(estimate_tokens(""), 0)

    def test_non_empty_never_estimates_zero(self):
        """A caller must never conclude a real prompt costs nothing."""
        self.assertGreaterEqual(estimate_tokens("x"), 1)

    def test_estimate_runs_high_not_low(self):
        """3.5 sits below the measured 3.56-4.03, so the estimate should
        exceed the real token count -- erring toward trimming early."""
        text = "x" * 3560          # ~1000 real tokens at the measured 3.56
        self.assertGreater(estimate_tokens(text), 1000)

    def test_scales_linearly(self):
        self.assertEqual(estimate_tokens("y" * 7000),
                         2 * estimate_tokens("y" * 3500))


class BudgetTests(unittest.TestCase):
    def test_budget_is_below_the_window(self):
        self.assertLess(token_budget(MODEL), context_window_for(MODEL))

    def test_output_reserve_shrinks_the_budget(self):
        self.assertLess(token_budget(MODEL, reserve_output_tokens=4000),
                        token_budget(MODEL, reserve_output_tokens=0))

    def test_budget_never_collapses_to_zero(self):
        self.assertGreaterEqual(
            token_budget("tiny:1b", reserve_output_tokens=10 ** 6), 256)

    def test_absurd_margin_is_clamped(self):
        self.assertGreater(token_budget(MODEL, safety_margin=5.0), 0)


class CheckTests(unittest.TestCase):
    def test_small_prompt_fits(self):
        result = check("hello", MODEL)
        self.assertTrue(result.fits)
        self.assertEqual(result.overflow_tokens, 0)
        self.assertIn("fits", result.describe())

    def test_huge_prompt_does_not_fit(self):
        result = check("x" * 400_000, MODEL)
        self.assertFalse(result.fits)
        self.assertGreater(result.overflow_tokens, 0)
        self.assertIn("exceeds", result.describe())

    def test_check_does_not_modify_anything(self):
        result = check("x" * 400_000, MODEL)
        self.assertFalse(result.trimmed)
        self.assertEqual(result.trimmed_chars, 0)

    def test_returns_the_documented_type(self):
        self.assertIsInstance(check("hi", MODEL), BudgetCheck)


class FitTests(unittest.TestCase):
    def test_fitting_prompt_is_returned_untouched(self):
        text, result = fit("short prompt", MODEL)
        self.assertEqual(text, "short prompt")
        self.assertFalse(result.trimmed)

    def test_over_long_prompt_is_trimmed_under_budget(self):
        text, result = fit("z" * 500_000, MODEL)
        self.assertTrue(result.trimmed)
        self.assertLessEqual(estimate_tokens(text), result.budget_tokens)

    def test_head_and_tail_both_survive(self):
        """Instructions live at the top, the question at the bottom. Losing
        either is what silent truncation does."""
        prompt = "HEAD_MARKER\n" + ("m" * 500_000) + "\nTAIL_MARKER"
        text, _ = fit(prompt, MODEL)
        self.assertIn("HEAD_MARKER", text)
        self.assertIn("TAIL_MARKER", text)

    def test_trimming_is_visible_in_the_text(self):
        text, _ = fit("q" * 500_000, MODEL)
        self.assertIn("trimmed from the middle", text)

    def test_trimmed_chars_is_accurate(self):
        original = "w" * 500_000
        text, result = fit(original, MODEL)
        self.assertGreater(result.trimmed_chars, 0)
        self.assertLess(len(text), len(original))

    def test_empty_prompt_is_handled(self):
        text, result = fit("", MODEL)
        self.assertEqual(text, "")
        self.assertFalse(result.trimmed)

    def test_unknown_model_trims_sooner(self):
        """An 8192 default must reject a prompt the 32768 window accepts."""
        prompt = "p" * 60_000
        self.assertTrue(check(prompt, MODEL).fits)
        self.assertFalse(check(prompt, "brand-new-model:70b").fits)


class FitCodeBlockTests(unittest.TestCase):
    def test_small_code_is_untouched(self):
        code = "def f():\n    return 1\n"
        self.assertEqual(fit_code_block(code, MODEL), code)

    def test_large_code_is_trimmed(self):
        code = "def f():\n    pass\n" + ("# pad\n" * 100_000)
        out = fit_code_block(code, MODEL)
        self.assertLess(len(out), len(code))
        self.assertIn("trimmed from the middle", out)

    def test_scaffolding_is_budgeted_for(self):
        """The instructions wrapped around the code carry the request; a
        bigger scaffold must leave less room for the code."""
        code = "c" * 400_000
        small = fit_code_block(code, MODEL, surrounding_chars=100)
        large = fit_code_block(code, MODEL, surrounding_chars=50_000)
        self.assertLess(len(large), len(small))

    def test_code_head_and_tail_survive(self):
        code = "TOP_OF_FILE\n" + ("k" * 400_000) + "\nEND_OF_FILE"
        out = fit_code_block(code, MODEL)
        self.assertIn("TOP_OF_FILE", out)
        self.assertIn("END_OF_FILE", out)


class AgentIntegrationTests(unittest.TestCase):
    """think() is the single chokepoint every agent passes through."""

    def test_agent_response_carries_the_trim_count(self):
        from saleha.agents.base_agent import AgentResponse
        self.assertEqual(AgentResponse(success=True, content="x").context_trimmed_chars, 0)

    def test_oversized_prompt_is_trimmed_before_the_provider_sees_it(self):
        from unittest.mock import MagicMock
        from saleha.agents.base_agent import BaseAgent

        provider = MagicMock()
        provider.generate.return_value = MagicMock(
            success=True, content="ok", response_time=0.1,
            tokens_used=1, error_message="")
        agent = BaseAgent(role="Test", model=MODEL, provider=provider)

        resp = agent.think("BEGIN\n" + ("x" * 500_000) + "\nEND")
        sent = provider.generate.call_args.kwargs["prompt"]

        self.assertLess(len(sent), 500_000)
        self.assertIn("BEGIN", sent)
        self.assertIn("END", sent)
        self.assertGreater(resp.context_trimmed_chars, 0)

    def test_normal_prompt_is_passed_through_unchanged(self):
        from unittest.mock import MagicMock
        from saleha.agents.base_agent import BaseAgent

        provider = MagicMock()
        provider.generate.return_value = MagicMock(
            success=True, content="ok", response_time=0.1,
            tokens_used=1, error_message="")
        agent = BaseAgent(role="Test", model=MODEL, provider=provider)

        resp = agent.think("just a normal prompt")
        self.assertIn("just a normal prompt",
                      provider.generate.call_args.kwargs["prompt"])
        self.assertEqual(resp.context_trimmed_chars, 0)

    def test_a_broken_guard_does_not_break_the_call(self):
        """A guard that kills the call it guards is worse than no guard."""
        from unittest.mock import MagicMock, patch
        from saleha.agents.base_agent import BaseAgent

        provider = MagicMock()
        provider.generate.return_value = MagicMock(
            success=True, content="ok", response_time=0.1,
            tokens_used=1, error_message="")
        agent = BaseAgent(role="Test", model=MODEL, provider=provider)

        with patch("saleha.core.context_budget.fit",
                   side_effect=RuntimeError("guard exploded")):
            resp = agent.think("hello")
        self.assertTrue(resp.success)
        self.assertEqual(resp.context_trimmed_chars, 0)


if __name__ == "__main__":
    unittest.main()
