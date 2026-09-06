"""
Saleha Core: Active Inference Gate (ask before guessing)

The idea, in one line
--------------------
If a goal is too vague to act on, measure that and ask one good question --
do not guess and write the wrong code confidently.

Why this exists
---------------
Measured on this repo before this module existed:

    PlannerAgent.create_plan("fix it")
      -> success=True, recommendation=EXECUTE, complexity 0.0
      -> steps: ['"main ise pragati karunga."']

No file named, no repo, no bug described -- and the planner reported success
and moved to execution. The planner branches on *complexity* (how big a task
is) and never on *specificity* (whether it is clear enough to start). Those
are different axes: "fix it" is trivially small and completely unactionable.

This is Karl Friston's Active Inference reduced to something a coding agent
can actually use: when uncertainty is high, take an epistemic action (ask,
or go look) instead of a confident wrong one.

What this is NOT
----------------
It is **not** a perplexity model, despite the design notes calling for one.
A real perplexity score needs logprobs, which the Ollama `/api/generate`
path used here does not return. Rather than fake a number and call it
entropy, this measures concrete, checkable properties of the goal text:

  - does it name a file, path, module or symbol?
  - does it say what should change, not just that something should?
  - does it carry a bare referent ("it", "this", "that") with no antecedent?
  - is there enough of it to act on at all?

Each is a real signal with a real reason to be there. The score they produce
is a heuristic and is documented as one -- it is not presented as a
mathematical measure of surprise.

Honest limits
-------------
- A goal can be perfectly specific and still wrong. This catches vagueness,
  not error.
- A goal can look vague and be perfectly clear in context (a follow-up in a
  session that already named the file). Callers that hold context should
  pass it via `context_has_target=True`, which suppresses the referent rule.
- The thresholds are judgement, tuned against the examples in the tests. They
  are not derived from a corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


# A bare referent with nothing to refer to: "fix it", "make this better".
_BARE_REFERENT = re.compile(
    r"^\s*(?:please\s+|pls\s+|just\s+)?"
    r"(?:can\s+you\s+|could\s+you\s+)?"
    r"(?:fix|repair|change|update|improve|refactor|handle|do|make|clean|sort)"
    r"\s+(?:it|this|that|them|these|those|things?|stuff)\b",
    re.IGNORECASE,
)

# Something that looks like a file, path, module or dotted symbol.
_TARGET_TOKEN = re.compile(
    r"(?:[\w./\\-]+\.(?:py|js|ts|tsx|jsx|go|rs|java|rb|c|h|cpp|sh|toml|ya?ml|json|md)\b)"
    r"|(?:\b\w+(?:\.\w+){1,}\b)"          # dotted path / module.symbol
    r"|(?:\b\w+_\w+\b)"                   # snake_case identifier
    r"|(?:`[^`]+`)",                      # anything the user backticked
    re.IGNORECASE,
)

# Verbs that say what kind of change is wanted.
_ACTION_WORDS = (
    "add", "remove", "rename", "write", "create", "delete", "fix", "refactor",
    "implement", "replace", "migrate", "convert", "optimise", "optimize",
    "parallelise", "parallelize", "test", "document", "extract", "inline",
    "split", "merge", "upgrade", "downgrade", "revert", "cache", "validate",
    "handle", "support", "expose", "log", "raise", "catch", "sort", "filter",
)

# Words that describe an observable outcome -- evidence the goal says what
# "done" looks like, not merely that something should happen.
_OUTCOME_HINTS = (
    "so that", "should", "must", "instead of", "rather than", "returns",
    "raises", "fails", "passes", "expects", "when ", "if ", "because",
)


@dataclass
class Uncertainty:
    """What was measured about a goal, and what to do about it."""

    goal: str
    score: float                       # 0.0 = actionable, 1.0 = unactionable
    actionable: bool
    reasons: List[str] = field(default_factory=list)
    question: str = ""                 # the one question worth asking
    signals: dict = field(default_factory=dict)

    @property
    def should_ask(self) -> bool:
        return not self.actionable


class ActiveInferenceGate:
    """
    Decide whether a goal is specific enough to act on.

    Deliberately conservative: the cost of a needless question is one round
    trip, and the cost of a confident wrong implementation is the user's
    trust plus whatever the wrong code broke. But it must not nag -- a goal
    that names a target and an action passes immediately.
    """

    # Tuned against the cases in the tests. Above this, ask.
    ASK_THRESHOLD = 0.6

    # Below this many words a goal almost never carries enough to act on,
    # unless it names a concrete target.
    MIN_WORDS = 4

    def assess(self, goal: Optional[str],
               context_has_target: bool = False) -> Uncertainty:
        """
        Measure how actionable `goal` is.

        `context_has_target`: the caller already knows what is being worked on
        (an open file, a prior turn that named it), so a bare "fix it" is
        legitimate. This suppresses the referent and target rules.
        """
        text = (goal or "").strip()
        words = text.split()

        has_target = bool(_TARGET_TOKEN.search(text)) or context_has_target
        lowered = text.lower()
        has_action = any(re.search(r"\b" + w + r"\b", lowered)
                         for w in _ACTION_WORDS)
        has_outcome = any(h in lowered for h in _OUTCOME_HINTS)
        bare_referent = bool(_BARE_REFERENT.search(text)) and not context_has_target

        reasons: List[str] = []
        score = 0.0

        if not text:
            return Uncertainty(
                goal=text, score=1.0, actionable=False,
                reasons=["the goal is empty"],
                question="What would you like me to do?",
                signals={"empty": True})

        if bare_referent:
            score += 0.55
            reasons.append('says "fix it"-style without naming what "it" is')

        if not has_target:
            score += 0.30
            reasons.append("names no file, module or symbol to change")

        if len(words) < self.MIN_WORDS and not has_target:
            score += 0.20
            reasons.append(f"only {len(words)} word(s) long")

        if not has_action:
            score += 0.15
            reasons.append("does not say what kind of change is wanted")

        if not has_outcome and not has_target:
            score += 0.10
            reasons.append("does not describe what a correct result looks like")

        # A goal with no concrete target and no stated outcome is unactionable
        # regardless of how the individual penalties add up. Without this,
        # "make the tests faster" (0.55, no action verb matched) slipped under
        # the threshold while the equally vague "optimize the parser" (0.60)
        # was caught -- a scoring artefact, not a real difference between them.
        if not has_target and not has_outcome and len(words) <= 6:
            score = max(score, self.ASK_THRESHOLD)
            if "too vague to start from" not in reasons:
                reasons.append("too vague to start from: no concrete target "
                               "and no description of the desired result")

        score = round(min(1.0, score), 3)
        actionable = score < self.ASK_THRESHOLD

        return Uncertainty(
            goal=text,
            score=score,
            actionable=actionable,
            reasons=reasons,
            question="" if actionable else self._question(
                text, has_target, has_action, bare_referent),
            signals={
                "has_target": has_target,
                "has_action": has_action,
                "has_outcome": has_outcome,
                "bare_referent": bare_referent,
                "words": len(words),
            },
        )

    @staticmethod
    def _question(goal: str, has_target: bool, has_action: bool,
                  bare_referent: bool) -> str:
        """
        One question, aimed at the biggest missing piece.

        Asking three questions at once is its own kind of unhelpful; pick the
        gap that blocks starting.
        """
        if bare_referent or not has_target:
            return ("Which file or function should I change? "
                    "(A path, or the symbol name, is enough.)")
        if not has_action:
            return f"What should change about {goal.strip().rstrip('?.')}?"
        return ("What should the result look like when it is correct? "
                "A failing case or expected output would be ideal.")


active_inference_gate = ActiveInferenceGate()


def assess_goal(goal: Optional[str],
                context_has_target: bool = False) -> Uncertainty:
    """Module-level convenience wrapper."""
    return active_inference_gate.assess(goal, context_has_target=context_has_target)
