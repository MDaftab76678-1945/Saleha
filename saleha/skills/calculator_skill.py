"""
Saleha Skills: Calculator Skill (example -- the first built-in skill)

Shows how the Skill pattern works: simple math questions ("What is 12 * 8?")
do not need to go through the LLM Plan->Code->Test pipeline -- Python can
solve them directly. That is:
  - faster (no Ollama call)
  - more reliable (a small model sometimes gets simple math wrong; this
    evaluator does not)

This is only an example; the same pattern could host a "file_read_skill",
a "unit_convert_skill" and so on.
"""

import re
import ast
import operator

from saleha.core.skill_base import Skill, SkillResult


# Safe operators only -- eval() is never used (security risk); a small
# safe expression evaluator is used instead.
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_evaluate_ast_node(node: ast.AST) -> float:
    """Recursively evaluates safe mathematical AST nodes."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("Only numeric constants allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_evaluate_ast_node(node.left), _safe_evaluate_ast_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_evaluate_ast_node(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


class CalculatorSkill(Skill):
    """Simple arithmetic solver without calling an external LLM."""

    name = "calculator"
    description = "Simple arithmetic (add/subtract/multiply/divide/power) solves it directly, without an LLM."

    # Extracts one clean math expression from the task text
    _EXPR_PATTERN = re.compile(r"[-+]?\d+(\.\d+)?(\s*[\+\-\*/\^]\s*[-+]?\d+(\.\d+)?)+")

    def can_handle(self, task: str) -> bool:
        """Determines if the given query is a direct arithmetic problem."""
        if any(kw in task.lower() for kw in ["function", "class", "script", "program", "code likho"]):
            return False
        return bool(self._EXPR_PATTERN.search(task))

    def execute(self, task: str) -> SkillResult:
        """Parses and computes the arithmetic expression safely."""
        match = self._EXPR_PATTERN.search(task)
        if not match:
            return SkillResult(success=False, output="", error="No arithmetic expression found in task.")

        expr = match.group(0).replace("^", "**")
        try:
            tree = ast.parse(expr, mode="eval")
            result = _safe_evaluate_ast_node(tree.body)
            # Format cleanly
            int_res = int(result) if result.is_integer() else result
            return SkillResult(success=True, output=f"{expr} = {int_res}")
        except Exception as e:
            return SkillResult(success=False, output="", error=f"Could not compute '{expr}': {e}")


if __name__ == "__main__":
    _skill = CalculatorSkill()
    _test_cases = [
        "What is 12 * 8?",
        "Calculate 100 / 4 + 5",
        "Create a function to add two numbers",
    ]
    for _task in _test_cases:
        _handled = _skill.can_handle(_task)
        if _handled:
            _res = _skill.execute(_task)