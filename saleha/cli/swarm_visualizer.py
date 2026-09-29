"""
Saleha CLI: Interactive ASCII Swarm Visualizer

Renders real-time multi-agent DAG topologies, node state transitions,
execution duration (ms), and engineering metrics in the terminal.
"""

from __future__ import annotations

import sys
import time
from typing import List
from saleha.core.swarm.swarm_pipeline_engine import SwarmPipelineStage, SwarmExecutionResult


class SwarmAsciiVisualizer:
    """ASCII Swarm DAG Visualizer."""

    ROLE_TAGS = {
        "Architect": "ARCH",
        "Designer": "DSGN",
        "WebDev": "WEB",
        "DataEngineer": "DATA",
        "Coder": "CODE",
        "SecurityGuard": "SEC",
        "QALead": "QA",
        "Reviewer": "REV",
        "FinOpsOptimizer": "FIN",
        "DevOps": "OPS",
        "SREIncident": "SRE",
        "NewSkillCreator": "SKILL",
    }

    def render_header(self, goal: str) -> None:
        print("\n" + "=" * 70)
        print("  SALEHA AUTONOMOUS MULTI-AGENT SWARM ENGINE v2.6.0")
        print(f"  Goal: {goal}")
        print("=" * 70)

    def render_stage_update(self, stage: SwarmPipelineStage, current_idx: int, total_stages: int) -> None:
        tag = self.ROLE_TAGS.get(stage.agent_role, "AGENT")
        status_badge = "[OK] SUCCESS" if stage.status == "success" else stage.status.upper()
        progress_bar = f"[{current_idx}/{total_stages}]"
        
        print(f"\n  {progress_bar} [{tag}] Agent: \033[1;36m{stage.agent_role}Agent\033[0m")
        print(f"     Status  : {status_badge}  ({stage.duration_ms}ms)")
        if stage.output_summary:
            print(f"     Output  : \033[0;32m{stage.output_summary}\033[0m")
        
        if current_idx < total_stages:
            print("        |")
            print("        v (EventBus Dispatch)")

    def render_execution_summary(self, result: SwarmExecutionResult) -> None:
        outcome = "COMPLETED SUCCESSFULLY" if result.success else "FAILED"
        print("\n" + "-" * 70)
        print(f"  SWARM PIPELINE {outcome}")
        print("-" * 70)
        print(f"  - Execution ID      : \033[1;33m{result.execution_id}\033[0m")
        print(f"  - Architecture ADR  : \033[1;32m{result.adr_title}\033[0m")
        # Built outside the f-string expressions: backslashes are not allowed
        # inside f-string expression parts before Python 3.12.
        security_label = "\033[1;32m0 CWEs Detected (PASS)\033[0m" if result.security_clean else "Issues found"
        tests_label = "\033[1;32mAll Invariant Tests Passed\033[0m" if result.tests_passed else "Failed"
        print(f"  - Security Audit    : {security_label}")
        print(f"  - Test Suite (QA)   : {tests_label}")
        print(f"  - Token Optimization: \033[1;36m{result.token_savings_pct}% context compressed\033[0m")
        print(f"  - Total Runtime     : \033[1;37m{result.total_duration_ms}ms\033[0m")
        print(f"  - Episodic Memories : \033[1;35m{result.memory_recalled_count} prior patterns recalled\033[0m")
        print("=" * 70 + "\n")


visualizer = SwarmAsciiVisualizer()
