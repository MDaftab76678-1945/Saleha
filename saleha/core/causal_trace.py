"""
Saleha Core: Causal Context Tracing

The question
------------
When an agent produces an answer after being handed retrieved memories, repo
context and tool observations, *which of those pieces actually caused the
answer*? Without an answer to that, context is added on faith and never
removed, and a piece that contributes nothing costs tokens forever.

Why this is not the notebook's version
--------------------------------------
`CausalMemoryTracer` (`chat-export-1780647227422.json`) answers it by
registering forward hooks on `model.transformer.h[...]` and replacing memory
token activations with a baseline, then measuring KL divergence between the
full and ablated output distributions. That is real activation patching, and
it is unusable here: Ollama's HTTP API exposes no activations, no logits and
no weights. I said so when I first read it, and that part was correct.

But the *causal* question does not require activation access. Ablation at the
input is a valid intervention too, and it is the one this architecture allows:

    1. Run the prompt with all context pieces  -> baseline answer
    2. Remove piece i, run again               -> counterfactual answer
    3. Influence of piece i = how much the answer changed

This is leave-one-out ablation. It is a coarser instrument than activation
patching -- it cannot say *where* in the network a memory mattered -- but it
answers the question that actually matters operationally: would dropping this
piece change what the agent does?

Honest limits
-------------
- **Cost.** N+1 model calls for N pieces. The pieces are independent of each
  other, so they are run concurrently through FastInference, but the token
  cost is real. This is a diagnostic, not something to run per request.
- **Sampling noise.** At temperature > 0 two identical calls differ, which
  would show up as spurious influence. Every call here is pinned to
  temperature 0 with a fixed seed, and `measure_noise_floor()` quantifies what
  is left so a caller can tell signal from jitter instead of assuming.
- **Interaction effects.** Leave-one-out attributes to single pieces. Two
  memories that only matter together will each look useless alone. Documented
  rather than hidden; `ablate_pairs()` exists for when that matters.
- Influence is a *similarity delta*, not a probability. It is comparable
  between pieces in one trace, not across traces.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

# Deterministic by construction: a difference caused by sampling is not a
# causal effect. See measure_noise_floor().
_DETERMINISTIC = {"temperature": 0.0, "top_p": 1.0, "seed": 7}


@dataclass
class ContextPiece:
    """One removable piece of context."""

    piece_id: str
    text: str
    kind: str = "memory"          # memory | repo | observation | instruction


@dataclass
class Influence:
    piece_id: str
    kind: str
    influence: float              # 0.0 = answer unchanged, 1.0 = fully changed
    ablated_answer: str = ""
    error: str = ""

    @property
    def measured(self) -> bool:
        return not self.error


@dataclass
class CausalTrace:
    goal: str
    baseline_answer: str
    influences: List[Influence] = field(default_factory=list)
    noise_floor: float = 0.0
    model: str = ""
    calls_made: int = 0

    @property
    def ranked(self) -> List[Influence]:
        """Most influential first; unmeasured pieces last."""
        return sorted([i for i in self.influences if i.measured],
                      key=lambda i: -i.influence)

    def above_noise(self) -> List[Influence]:
        """Pieces whose influence exceeds the measured noise floor."""
        return [i for i in self.ranked if i.influence > self.noise_floor]

    def dead_weight(self) -> List[Influence]:
        """
        Pieces that did not change the answer at all.

        These are the ones worth dropping: they cost tokens and buy nothing.
        A piece at or below the noise floor is indistinguishable from one that
        was never read.
        """
        return [i for i in self.ranked if i.influence <= self.noise_floor]

    def describe(self) -> str:
        if not self.influences:
            return "no context pieces to trace"
        lines = [f"noise floor {self.noise_floor:.4f} "
                 f"({self.calls_made} calls, {self.model})"]
        for inf in self.ranked:
            mark = "*" if inf.influence > self.noise_floor else " "
            lines.append(f" {mark} {inf.influence:.4f}  {inf.kind}:{inf.piece_id}")
        return "\n".join(lines)


def answer_distance(a: str, b: str) -> float:
    """
    How much two answers differ, in 0.0-1.0.

    Token-set aware rather than raw character diff: reordered but equivalent
    output should not read as a large causal effect. This is the stand-in for
    the KL divergence the activation-patching version uses -- weaker, and
    named as such, because output distributions are not available here.
    """
    if a == b:
        return 0.0
    if not a and not b:
        return 0.0
    if not a or not b:
        return 1.0
    ratio = difflib.SequenceMatcher(
        None, re.findall(r"\w+", a.lower()), re.findall(r"\w+", b.lower())
    ).ratio()
    return round(1.0 - ratio, 6)


class CausalTracer:
    """
    Leave-one-out ablation over the context pieces of a single prompt.

    The prompt is rebuilt from pieces rather than edited as a string, so an
    ablation removes exactly one piece and nothing else.
    """

    def __init__(self, inference: Optional[Any] = None,
                 model: str = "qwen2.5-coder:3b",
                 num_predict: int = 400):
        self._inference = inference
        self.model = model
        self.num_predict = num_predict

    def _engine(self):
        if self._inference is None:
            from saleha.core.fast_inference import FastInference
            self._inference = FastInference()
        return self._inference

    @staticmethod
    def build_prompt(goal: str, pieces: Sequence[ContextPiece],
                     skip: Optional[str] = None) -> str:
        blocks = [f"{p.kind}: {p.text}" for p in pieces if p.piece_id != skip]
        context = "\n\n".join(blocks)
        if context:
            return f"Context:\n{context}\n\nTask: {goal}"
        return f"Task: {goal}"

    def _request(self, prompt: str, tag: str):
        from saleha.core.fast_inference import InferenceRequest
        return InferenceRequest(
            prompt=prompt, model=self.model, tag=tag,
            options={**_DETERMINISTIC, "num_predict": self.num_predict})

    def measure_noise_floor(self, goal: str,
                            pieces: Sequence[ContextPiece],
                            samples: int = 2) -> float:
        """
        Run the SAME prompt several times and measure how much the answer
        varies anyway.

        Anything at or below this is jitter, not causation. Without it a
        reported influence of 0.03 is meaningless -- it could be the model
        being the model.
        """
        if samples < 2:
            return 0.0
        prompt = self.build_prompt(goal, pieces)
        results = self._engine().run_batch(
            [self._request(prompt, f"noise{i}") for i in range(samples)],
            use_cache=False)
        answers = [r.content for r in results if r.success]
        if len(answers) < 2:
            return 0.0
        return max(answer_distance(answers[0], other) for other in answers[1:])

    def trace(self, goal: str, pieces: Sequence[ContextPiece],
              noise_samples: int = 2) -> CausalTrace:
        """
        Measure each piece's causal contribution to the answer.

        Ablations are independent of one another, so they go out concurrently.
        The baseline must be established first -- everything is measured
        against it -- which is a real data dependency, not a missed
        optimisation.
        """
        pieces = list(pieces)
        engine = self._engine()
        calls = 0

        baseline_result = engine.run(
            self._request(self.build_prompt(goal, pieces), "baseline"),
            use_cache=False)
        calls += 1
        if not baseline_result.success:
            return CausalTrace(goal=goal, baseline_answer="", model=self.model,
                               calls_made=calls,
                               influences=[Influence(p.piece_id, p.kind, 0.0,
                                                     error="baseline call failed")
                                           for p in pieces])
        baseline = baseline_result.content

        noise = 0.0
        if noise_samples >= 2:
            noise = self.measure_noise_floor(goal, pieces, samples=noise_samples)
            calls += noise_samples

        if not pieces:
            return CausalTrace(goal=goal, baseline_answer=baseline,
                               noise_floor=noise, model=self.model,
                               calls_made=calls)

        requests = [
            self._request(self.build_prompt(goal, pieces, skip=p.piece_id),
                          p.piece_id)
            for p in pieces
        ]
        results = engine.run_batch(requests, use_cache=False)
        calls += len(requests)
        by_tag = {r.tag: r for r in results}

        influences: List[Influence] = []
        for piece in pieces:
            result = by_tag.get(piece.piece_id)
            if result is None or not result.success:
                influences.append(Influence(
                    piece.piece_id, piece.kind, 0.0,
                    error=(result.error if result else "no result")))
                continue
            influences.append(Influence(
                piece_id=piece.piece_id,
                kind=piece.kind,
                influence=answer_distance(baseline, result.content),
                ablated_answer=result.content,
            ))

        return CausalTrace(goal=goal, baseline_answer=baseline,
                           influences=influences, noise_floor=noise,
                           model=self.model, calls_made=calls)

    def ablate_pairs(self, goal: str, pieces: Sequence[ContextPiece],
                     baseline_answer: str) -> Dict[str, float]:
        """
        Remove pieces two at a time.

        Leave-one-out misses interaction: two memories that only matter
        together each look useless alone. This is the check for that, kept
        separate because it costs O(n^2) calls.
        """
        pieces = list(pieces)
        pairs = [(a, b) for i, a in enumerate(pieces) for b in pieces[i + 1:]]
        if not pairs:
            return {}
        requests = []
        for a, b in pairs:
            kept = [p for p in pieces if p.piece_id not in (a.piece_id, b.piece_id)]
            requests.append(self._request(
                self.build_prompt(goal, kept), f"{a.piece_id}+{b.piece_id}"))
        results = self._engine().run_batch(requests, use_cache=False)
        return {
            r.tag: answer_distance(baseline_answer, r.content)
            for r in results if r.success
        }
