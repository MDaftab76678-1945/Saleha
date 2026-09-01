"""
Saleha Skills: Calculator Skill (Example -- pehla built-in skill)

Ye dikhata hai Skill pattern kaise kaam karta hai: simple math questions
("What is 12 * 8?") ko LLM ke through Plan->Code->Test bhejne ki zaroorat
nahi -- seedha Python se solve ho sakta hai. Isse:
  - Zyada fast (koi Ollama call nahi)
  - Zyada bharosemand (chhota model kabhi-kabhi simple math bhi galat
    kar deta hai, ye kabhi galat nahi hoga)

Ye sirf ek udaharan hai -- isi pattern se future me "file_read_skill",
"unit_convert_skill", jaisi cheezein bhi add ki ja sakti hain.
"""

import re
import ast
import operator

from saleha.core.skill_base import Skill, SkillResult


# Safe operators only -- eval() bilkul use nahi karte (security risk),
# iske bajaye ek chhota safe expression evaluator likha hai.
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
    description = "Simple arithmetic (add/subtract/multiply/divide/power) seedha solve karta hai, LLM ke bina."

    # Task me se ek clean math expression nikaalne ke liye
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