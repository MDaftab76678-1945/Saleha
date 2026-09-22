"""
Saleha Workflow Engine: Autonomous Self-Healing Node.

Wraps any workflow node with an Active Inference error-recovery loop that intercepts
runtime exceptions, schema mismatches, and data drift, autonomously synthesizing
surgical in-memory adaptations to prevent workflow failure.
"""

from __future__ import annotations

import difflib
import traceback
from typing import Any, Callable, Dict, List, Optional

from saleha.core.workflow.nodes import NodeStatus, WorkflowExecutionContext, WorkflowNode


class SelfHealingNode(WorkflowNode):
    """
    Active-Inference self-repair node wrapper.
    Eliminates n8n's primary shortcoming: brittle failure on schema drift or runtime errors.
    """

    def __init__(
        self,
        inner_node: WorkflowNode,
        max_repair_attempts: int = 2,
        custom_healer: Optional[Callable[[Exception, Dict[str, Any], WorkflowExecutionContext], Optional[Dict[str, Any]]]] = None,
    ) -> None:
        super().__init__(
            node_id=inner_node.id,
            title=f"{inner_node.title} (Self-Healing)",
            node_type="self_healing",
            depends_on=inner_node.depends_on,
            config=inner_node.config,
        )
        self.inner_node = inner_node
        self.max_repair_attempts = max_repair_attempts
        self.custom_healer = custom_healer
        self.repair_history: List[Dict[str, Any]] = []

    def _diagnose_and_heal_inputs(
        self,
        exc: Exception,
        inputs: Dict[str, Any],
        context: WorkflowExecutionContext,
    ) -> Optional[Dict[str, Any]]:
        """
        Synthesizes an input adapter when a KeyError or TypeError occurs
        due to upstream schema changes or renamed keys.
        """
        if isinstance(exc, KeyError):
            missing_key = str(exc).strip("'\"")
            # Find closest matching key in inputs
            all_keys = list(inputs.keys())
            close_matches = difflib.get_close_matches(missing_key, all_keys, n=1, cutoff=0.5)
            if close_matches:
                repaired_inputs = dict(inputs)
                repaired_inputs[missing_key] = inputs[close_matches[0]]
                context.log(
                    f"Self-Healing [KeyError]: Aliased missing key '{missing_key}' "
                    f"from '{close_matches[0]}'"
                )
                return repaired_inputs
            # No similar key: inventing a None value would hide the failure.
            return None

        if isinstance(exc, TypeError):
            # Attempt type coercion if input string needs to be int or vice-versa
            err_msg = str(exc)
            if "int" in err_msg or "float" in err_msg or "str" in err_msg:
                repaired_inputs = dict(inputs)
                for k, v in list(repaired_inputs.items()):
                    if isinstance(v, str) and v.isdigit():
                        repaired_inputs[k] = int(v)
                    elif isinstance(v, (int, float)):
                        repaired_inputs[f"{k}_str"] = str(v)
                context.log(f"Self-Healing [TypeError]: Applied type coercion heuristics: {err_msg}")
                return repaired_inputs

        return None

    def execute(self, context: WorkflowExecutionContext) -> Dict[str, Any]:
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.max_repair_attempts:
            try:
                if attempt == 0:
                    out = self.inner_node.execute(context)
                    self.status = NodeStatus.COMPLETED
                    self.outputs = out
                    return out
                else:
                    # Retry with healed state
                    context.log(
                        f"Self-Healing: Re-executing node '{self.inner_node.id}' (Attempt {attempt + 1})"
                    )
                    out = self.inner_node.execute(context)
                    self.status = NodeStatus.HEALED
                    self.outputs = out
                    self.metadata["healed"] = True
                    self.metadata["repair_history"] = self.repair_history
                    context.log(f"Self-Healing [SUCCESS]: Node '{self.inner_node.id}' successfully recovered!")
                    return out

            except Exception as exc:
                last_error = exc
                attempt += 1
                tb = traceback.format_exc()
                diagnostic = {
                    "attempt": attempt,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback_summary": tb.splitlines()[-3:],
                }
                self.repair_history.append(diagnostic)
                context.log(
                    f"Self-Healing: Intercepted {type(exc).__name__} in node '{self.inner_node.id}': {exc}"
                )

                if attempt > self.max_repair_attempts:
                    break

                # 1. Custom healer check
                if self.custom_healer:
                    try:
                        resolved = self.custom_healer(exc, self.inner_node.inputs, context)
                        if resolved is not None:
                            self.inner_node.inputs = resolved
                            continue
                    except Exception as healer_err:
                        context.log(f"Self-Healing: Custom healer failed: {healer_err}")

                # 2. Heuristic schema & type healing
                current_inputs = self.inner_node.resolve_inputs(context)
                healed_inputs = self._diagnose_and_heal_inputs(exc, current_inputs, context)
                if healed_inputs is not None:
                    # Patch context node output for upstream dependency to satisfy contract
                    for dep_id in self.inner_node.depends_on:
                        dep_data = context.get_output(dep_id)
                        if isinstance(dep_data, dict):
                            for hk, hv in healed_inputs.items():
                                if hk not in dep_data:
                                    dep_data[hk] = hv
                    continue

                break

        # If repairs failed, propagate genuine failure
        self.status = NodeStatus.FAILED
        self.error = f"Self-healing exhausted {self.max_repair_attempts} attempts: {str(last_error)}"
        self.metadata["repair_history"] = self.repair_history
        raise RuntimeError(self.error) from last_error
