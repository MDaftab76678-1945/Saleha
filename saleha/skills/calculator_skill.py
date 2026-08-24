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
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
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


def _safe_eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


class CalculatorSkill(Skill):
    name = "calculator"
    description = "Simple arithmetic (add/subtract/multiply/divide/power) seedha solve karta hai, LLM ke bina."

    # Task me se ek clean math expression nikaalne ke liye
    _EXPR_PATTERN = re.compile(r"[-+]?\d+(\.\d+)?(\s*[\+\-\*/\^]\s*[-+]?\d+(\.\d+)?)+")

    def can_handle(self, task: str) -> bool:
        # Sirf tab handle karo jab task me koi clean arithmetic expression ho
        # AUR task "function likho" jaisi coding request na ho (wo Coder ka kaam hai)
        if any(kw in task.lower() for kw in ["function", "class", "script", "program", "code likho"]):
            return False
        return bool(self._EXPR_PATTERN.search(task))

    def execute(self, task: str) -> SkillResult:
        match = self._EXPR_PATTERN.search(task)
        if not match:
            return SkillResult(success=False, output="", error="No arithmetic expression found in task.")

        expr = match.group(0).replace("^", "**")
        try:
            tree = ast.parse(expr, mode="eval")
            result = _safe_eval(tree.body)
            return SkillResult(success=True, output=f"{expr} = {result}")
        except Exception as e:
            return SkillResult(success=False, output="", error=f"Could not evaluate '{expr}': {e}")


if __name__ == "__main__":
    skill = CalculatorSkill()

    test_cases = [
        "What is 12 * 8?",
        "Calculate 100 / 4 + 5",
        "Create a function to add two numbers",  # ye Coder ke paas jaana chahiye, calculator ke nahi
    ]

    for task in test_cases:
        handled = skill.can_handle(task)
        print(f"Task: '{task}' -> can_handle: {handled}")
        if handled:
            result = skill.execute(task)
            print(f"  Result: {result.output if result.success else result.error}")