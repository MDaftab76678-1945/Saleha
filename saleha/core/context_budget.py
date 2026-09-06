"""
Saleha Core: Context Budget Guard

The failure this prevents
------------------------
Measured on this box against qwen2.5-coder:3b (32768-token context, no
`num_ctx` override anywhere in the repo):

    prompt   54 KB  -> answer recalled correctly
    prompt  280 KB  -> success=True, answer LOST  ("Magic is the magic word.")
    prompt  840 KB  -> success=True, answer LOST  ('The magic word is "yes".')

The magic word was placed at the START of the prompt and the question at the
END. Past the window Ollama silently drops the middle: no error, no warning,
`success=True`, and a confident wrong answer. Nothing downstream can tell that
from a real answer.

`repo_context_packer.pack()` already budgets its own output (6000 chars), but
four agents interpolate `{code}` straight into a prompt with no bound at all
(coder, debugger, qa_lead, reviewer). A single large file silently degrades
those calls.

What this does
--------------
Estimates prompt size, and when it will not fit:
  - says so explicitly (callers can refuse rather than get a bad answer), and
  - trims from the MIDDLE, keeping the head and tail, with a visible marker.

Middle-out is deliberate. A code prompt's instructions sit at the top and the
question at the bottom; the middle is the most droppable part, and dropping it
visibly is strictly better than the model dropping it silently.

On token estimation
-------------------
Pulling in tiktoken would be wrong -- different vocabulary from Qwen -- so
this uses a chars-per-token ratio, which is an ESTIMATE and is named as one.

Measured against qwen2.5-coder:3b's own tokenizer, via the `prompt_eval_count`
that /api/generate reports back, on three files of this repo's source:

    5051 chars / 1420 tokens = 3.56
    6000 chars / 1489 tokens = 4.03
    6000 chars / 1553 tokens = 3.86

So 3.5 is used: below the measured range, which makes the estimate run high
and trim slightly early. `DEFAULT_SAFETY_MARGIN` then holds back a further
20% for the reply and for estimation error. Being wrong is cheap in one
direction (a slightly shorter prompt) and expensive in the other (silent
truncation), so this deliberately errs toward trimming.

If an exact count is ever needed, `prompt_eval_count` in the /api/generate
response is the real number -- but it only arrives after the call, which is
too late to decide whether to make it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Chars per token. An estimate -- see the module docstring. Code is denser
# than prose, so this runs lower than the usual "4 chars per token" figure.
CHARS_PER_TOKEN = 3.5

# Fraction of the window held back for the model's reply plus estimation
# error. The prompt gets the rest.
DEFAULT_SAFETY_MARGIN = 0.20

# Context windows for models this repo actually runs, read from
# `ollama show`. Unknown models fall back to the conservative default rather
# than an optimistic guess.
KNOWN_CONTEXT_WINDOWS = {
    "qwen2.5-coder:3b": 32768,
    "qwen2.5-coder:7b": 32768,
    "qwen3:8b": 40960,
    "deepseek-coder:6.7b": 16384,
    "llama3.1:8b": 131072,
}
DEFAULT_CONTEXT_WINDOW = 8192

_TRIM_MARKER = (
    "\n\n... [{dropped} characters trimmed from the middle to fit the "
    "context window -- {kept} kept] ...\n\n"
)


@dataclass
class BudgetCheck:
    """What was measured about a prompt, and what was done about it."""

    fits: bool
    original_chars: int
    estimated_tokens: int
    budget_tokens: int
    context_window: int
    model: str
    trimmed: bool = False
    trimmed_chars: int = 0

    @property
    def overflow_tokens(self) -> int:
        return max(0, self.estimated_tokens - self.budget_tokens)

    def describe(self) -> str:
        if self.fits:
            return (f"{self.estimated_tokens} est. tokens of "
                    f"{self.budget_tokens} budget ({self.model}) -- fits")
        return (f"{self.estimated_tokens} est. tokens exceeds the "
                f"{self.budget_tokens}-token budget for {self.model} "
                f"(window {self.context_window}) by ~{self.overflow_tokens}")


def context_window_for(model: Optional[str]) -> int:
    """
    Context window for a model, by exact name then by family prefix.

    Unknown models get DEFAULT_CONTEXT_WINDOW, not an optimistic guess: being
    wrong high here means silent truncation, which is the whole failure this
    module exists to prevent.
    """
    name = (model or "").strip()
    if name in KNOWN_CONTEXT_WINDOWS:
        return KNOWN_CONTEXT_WINDOWS[name]
    base = name.split(":")[0]
    for known, window in KNOWN_CONTEXT_WINDOWS.items():
        if known.split(":")[0] == base:
            return window
    return DEFAULT_CONTEXT_WINDOW


def estimate_tokens(text: str) -> int:
    """
    Rough token count. An ESTIMATE -- see the module docstring.

    Never returns 0 for non-empty text, so a caller cannot conclude that a
    non-empty prompt costs nothing.
    """
    if not text:
        return 0
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def token_budget(model: str, reserve_output_tokens: int = 0,
                 safety_margin: float = DEFAULT_SAFETY_MARGIN) -> int:
    """Tokens available to the prompt after the reply reserve and margin."""
    window = context_window_for(model)
    usable = int(window * (1.0 - max(0.0, min(0.9, safety_margin))))
    return max(256, usable - max(0, reserve_output_tokens))


def check(prompt: str, model: str, reserve_output_tokens: int = 0) -> BudgetCheck:
    """Measure a prompt against the budget without changing it."""
    est = estimate_tokens(prompt)
    budget = token_budget(model, reserve_output_tokens)
    return BudgetCheck(
        fits=est <= budget,
        original_chars=len(prompt or ""),
        estimated_tokens=est,
        budget_tokens=budget,
        context_window=context_window_for(model),
        model=model,
    )


def fit(prompt: str, model: str, reserve_output_tokens: int = 0):
    """
    Trim a prompt to fit, keeping the head and tail.

    Returns `(text, BudgetCheck)`. When trimming happens the result carries a
    visible marker saying how much was dropped -- an over-long prompt is
    already being cut by the runtime, and the only question is whether anyone
    can tell. `check.trimmed` lets a caller refuse instead.
    """
    result = check(prompt, model, reserve_output_tokens)
    if result.fits or not prompt:
        return prompt, result

    keep_chars = int(result.budget_tokens * CHARS_PER_TOKEN)
    # Leave room for the marker itself, or trimming could still overflow.
    keep_chars = max(200, keep_chars - 160)
    head = keep_chars // 2
    tail = keep_chars - head
    dropped = len(prompt) - keep_chars

    trimmed_text = (
        prompt[:head]
        + _TRIM_MARKER.format(dropped=dropped, kept=keep_chars)
        + prompt[-tail:]
    )
    result.trimmed = True
    result.trimmed_chars = dropped
    return trimmed_text, result


def fit_code_block(code: str, model: str, reserve_output_tokens: int = 512,
                   surrounding_chars: int = 1200) -> str:
    """
    Trim just the code portion of a prompt.

    `surrounding_chars` is the caller's own prompt scaffolding -- the
    instructions and question wrapped around the code. Budgeting for it
    matters: the scaffolding is the part that must not be lost, since it
    carries the actual request.
    """
    budget = token_budget(model, reserve_output_tokens)
    budget -= estimate_tokens(" " * max(0, surrounding_chars))
    budget = max(256, budget)
    if estimate_tokens(code) <= budget:
        return code
    keep = max(200, int(budget * CHARS_PER_TOKEN) - 160)
    head = keep // 2
    tail = keep - head
    return (code[:head]
            + _TRIM_MARKER.format(dropped=len(code) - keep, kept=keep)
            + code[-tail:])
