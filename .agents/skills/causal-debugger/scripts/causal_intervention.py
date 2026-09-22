#!/usr/bin/env python3
"""Pearl's Causal Interventional Debugger ($do$-calculus).

Isolates true defect root causes by performing counterfactual state interventions
and computing Average Causal Effects (ACE) across variable dimensions.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from typing import Dict, List, Any


class SafeExpressionEvaluator(ast.NodeVisitor):
    """Safely evaluates arithmetic and comparison expressions without arbitrary code execution."""

    def __init__(self, context: Dict[str, Any]) -> None:
        self.context = context

    def eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            if node.id in self.context:
                return self.context[node.id]
            raise NameError(f"Undefined variable in causal context: {node.id}")
        elif isinstance(node, ast.UnaryOp):
            val = self.eval_node(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +val
            elif isinstance(node.op, ast.USub):
                return -val
            elif isinstance(node.op, ast.Not):
                return not val
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(self.eval_node(v) for v in node.values)
            elif isinstance(node.op, ast.Or):
                return any(self.eval_node(v) for v in node.values)
        elif isinstance(node, ast.BinOp):
            left = self.eval_node(node.left)
            right = self.eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, (ast.Div, ast.FloorDiv)):
                return left // right if isinstance(node.op, ast.FloorDiv) else left / right
        elif isinstance(node, ast.Compare):
            left = self.eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self.eval_node(comparator)
                if isinstance(op, ast.Gt) and not (left > right):
                    return False
                elif isinstance(op, ast.GtE) and not (left >= right):
                    return False
                elif isinstance(op, ast.Lt) and not (left < right):
                    return False
                elif isinstance(op, ast.LtE) and not (left <= right):
                    return False
                elif isinstance(op, ast.Eq) and not (left == right):
                    return False
                elif isinstance(op, ast.NotEq) and not (left != right):
                    return False
                left = right
            return True

        raise ValueError(f"Unsupported AST node in safe causal eval: {type(node).__name__}")


def evaluate_assertion(expr_str: str, state: Dict[str, Any]) -> bool:
    """Evaluates expression under state context."""
    tree = ast.parse(expr_str, mode="eval")
    evaluator = SafeExpressionEvaluator(state)
    return bool(evaluator.eval_node(tree.body))


def compute_causal_effects(expr_str: str, failing_state: Dict[str, Any]) -> Dict[str, Any]:
    """Computes Average Causal Effect (ACE) for each variable via counterfactual interventions."""
    try:
        baseline = evaluate_assertion(expr_str, failing_state)
    except Exception as e:
        return {"status": "ERROR", "message": f"Baseline eval error: {e}"}

    causal_report: Dict[str, Any] = {}
    variables = list(failing_state.keys())

    for var in variables:
        current_val = failing_state[var]
        # Generate counterfactual candidate values
        counterfactuals = []
        if isinstance(current_val, (int, float)):
            counterfactuals = [
                current_val + 1,
                current_val - 1,
                current_val * 2,
                0,
                10,
                100,
                -current_val,
            ]
        elif isinstance(current_val, bool):
            counterfactuals = [not current_val]
        elif isinstance(current_val, str):
            counterfactuals = ["", "test", current_val + "_mod"]

        success_count = 0
        total_interventions = len(counterfactuals)

        for cf_val in counterfactuals:
            perturbed_state = dict(failing_state)
            perturbed_state[var] = cf_val
            try:
                outcome = evaluate_assertion(expr_str, perturbed_state)
                if outcome != baseline:
                    success_count += 1
            except Exception:
                continue

        ace = (success_count / max(total_interventions, 1)) if total_interventions > 0 else 0.0
        causal_report[var] = {
            "failing_value": current_val,
            "tested_interventions": total_interventions,
            "outcome_flips": success_count,
            "average_causal_effect": round(ace, 3),
        }

    # Rank by causal effect
    ranked_causes = sorted(
        causal_report.items(),
        key=lambda item: item[1]["average_causal_effect"],
        reverse=True,
    )

    top_cause = ranked_causes[0][0] if ranked_causes else None
    return {
        "status": "COMPLETED",
        "expression": expr_str,
        "baseline_outcome": baseline,
        "primary_root_cause_variable": top_cause,
        "causal_rankings": ranked_causes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pearl's Causal Interventional Debugger ($do$-calculus)."
    )
    parser.add_argument("--expr", "-e", required=True, help="Assertion expression to analyze.")
    parser.add_argument("--state", "-s", required=True, help="JSON string of failing variable values.")
    parser.add_argument("--output", "-o", default=None, help="Save report to JSON.")

    args = parser.parse_args()
    try:
        failing_state = json.loads(args.state)
    except Exception as e:
        sys.stderr.write(f"Error parsing JSON state: {e}\n")
        return 1

    report = compute_causal_effects(args.expr, failing_state)
    output_str = json.dumps(report, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"Causal diagnostic saved to: {args.output}")
    else:
        print(output_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
