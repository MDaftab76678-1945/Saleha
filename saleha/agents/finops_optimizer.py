"""
Saleha Agents: FinOps & Token Optimizer Agent

Makes a prompt or code smaller without changing its meaning -- blank-line
runs collapsed, `# TODO:` lines dropped, and for Python the imports nothing
uses removed (kept only if the result still compiles) -- and reports only
the techniques that changed something. Token counts are estimates (chars/4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from saleha.agents.base_agent import BaseAgent

# A projection needs a call volume, and this project has never measured one.
# Named here rather than buried as a literal so anyone printing a projected
# figure has to acknowledge the assumption it rests on.
PROJECTION_CALLS_PER_YEAR = 1_000_000


@dataclass
class FinOpsOptimizationResult:
    original_tokens_est: int
    optimized_tokens_est: int
    token_savings_pct: float
    optimized_payload: str
    saved_tokens_est: int
    savings_per_call_usd: float
    projection_call_volume: int
    techniques_applied: List[str]

    @property
    def projected_annual_usd(self) -> float:
        """Hypothetical, not measured: per-call saving x an assumed volume.

        Kept as a property rather than a stored field so it cannot be
        mistaken for something observed. Any caller rendering this must say
        it is a projection and name the volume it assumes
        (`projection_call_volume`).
        """
        return round(self.savings_per_call_usd * self.projection_call_volume, 2)


def drop_unused_imports(code: str) -> Tuple[str, List[str]]:
    """(code without its unused top-level imports, names dropped). Unchanged unless the result compiles."""
    import ast
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, []
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    exported = {elt.value for n in tree.body if isinstance(n, ast.Assign)
                for t in n.targets if isinstance(t, ast.Name) and t.id == "__all__"
                for elt in getattr(n.value, "elts", []) if isinstance(elt, ast.Constant)}
    rows = code.split("\n")
    dropped: List[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)) or node.lineno != node.end_lineno:
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        names = [(a.asname or a.name).split(".")[0] for a in node.names]
        if any(n == "*" for n in names) or any(n in used or n in exported for n in names):
            continue
        dropped += names
        rows[node.lineno - 1] = ""
    if not dropped:
        return code, []
    new = re.sub(r"\n{3,}", "\n\n", "\n".join(rows)).strip()
    try:
        compile(new, "<finops>", "exec")
    except SyntaxError:
        return code, []
    return new, dropped


class FinOpsOptimizerAgent(BaseAgent):
    """Lead FinOps & Token Economics Optimization Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="FinOpsOptimizer", model=model)

    def compress_and_optimize(self, text_or_code: str) -> FinOpsOptimizationResult:
        """Smaller text with the same meaning: blank runs, TODO lines and (Python) unused imports removed."""
        orig_tokens = max(1, len(text_or_code) // 4)
        # Only what was actually done is listed. This used to name four
        # techniques for every input -- "Prefix KV-Cache Alignment" and
        # "Context Window Budget Compression" among them -- none of which
        # this method implements.
        techniques: List[str] = []

        # 1. Collapse runs of blank lines
        cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", text_or_code)
        if cleaned != text_or_code:
            techniques.append("blank-line collapse")
        # 2. Strip `# TODO:` comment lines
        stripped = re.sub(r"^\s*#\s+TODO:.*$", "", cleaned, flags=re.MULTILINE)
        if stripped != cleaned:
            techniques.append("TODO comment removal")
        cleaned = stripped.strip()
        # 3. Python only: drop imports nothing uses -- kept only when the result still compiles
        pruned, dropped = drop_unused_imports(cleaned)
        if dropped:
            cleaned = pruned
            techniques.append(f"unused import removal ({', '.join(dropped)})")

        opt_tokens = max(1, len(cleaned) // 4)
        savings_pct = max(0.0, round(((orig_tokens - opt_tokens) / orig_tokens) * 100, 2))

        # What is actually known: how many estimated tokens this one call
        # saved. Nothing here measures how often the caller runs.
        #
        # This used to multiply by a hardcoded 1_000_000 calls/yr and return
        # the product as `annual_cost_savings_usd` -- a dollar figure with an
        # invented denominator, which then reached a real GitHub PR body via
        # the FinOps stage summary ("Saved ~$10.00/yr"). Measured: stripping
        # five tokens of whitespace produced "$10.00/yr" on the strength of a
        # call volume nobody had counted.
        #
        # The per-call saving is real and is reported. The projection is kept
        # only because callers read it, but it now carries its own assumption
        # in the field name instead of hiding it in a comment, so no caller
        # can print it as a measured saving.
        saved_tokens = max(0, orig_tokens - opt_tokens)
        cost_per_1k_usd = 0.002
        savings_per_call_usd = round((saved_tokens / 1000) * cost_per_1k_usd, 6)

        return FinOpsOptimizationResult(
            original_tokens_est=orig_tokens,
            optimized_tokens_est=opt_tokens,
            token_savings_pct=savings_pct,
            optimized_payload=cleaned,
            saved_tokens_est=saved_tokens,
            savings_per_call_usd=savings_per_call_usd,
            projection_call_volume=PROJECTION_CALLS_PER_YEAR,
            techniques_applied=techniques
        )
