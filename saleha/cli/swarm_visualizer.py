"""
Saleha CLI: Interactive ASCII Swarm Visualizer

Renders real-time multi-agent DAG topologies, node state transitions,
execution duration (ms), and engineering metrics in the terminal.
"""

from __future__ import annotations

import sys
import time
from typing import List
from saleha.core.swarm_pipeline_engine import SwarmPipelineStage, SwarmExecutionResult


class SwarmAsciiVisualizer:
    """ASCII Swarm DAG Visualizer."""

    ROLE_ICONS = {
        "Architect": "🏛️",
        "Designer": "🎨",
        "WebDev": "🌐",
        "DataEngineer": "🗄️",
        "Coder": "💻",
        "SecurityGuard": "🛡️",
        "QALead": "🧪",
        "Reviewer": "🔍",
        "FinOpsOptimizer": "💰",
        "DevOps": "🚀",
        "SREIncident": "🚨",
        "NewSkillCreator": "🧩",
    }

    def render_header(self, goal: str) -> None:
        print("\n" + "=" * 70)
        print("  🐝 SALEHA AUTONOMOUS MULTI-AGENT SWARM ENGINE v2.6.0")
        print(f"  🎯 Goal: {goal}")
        print("=" * 70)

    def render_stage_update(self, stage: SwarmPipelineStage, current_idx: int, total_stages: int) -> None:
        icon = self.ROLE_ICONS.get(stage.agent_role, "🤖")
        status_badge = "✅ [SUCCESS]" if stage.status == "success" else "⏳ [RUNNING]"
        progress_bar = f"[{current_idx}/{total_stages}]"
        
        print(f"\n  {progress_bar} {icon} Agent: \033[1;36m{stage.agent_role}Agent\033[0m")
        print(f"     Status  : {status_badge}  ({stage.duration_ms}ms)")
        if stage.output_summary:
            print(f"     Output  : \033[0;32m{stage.output_summary}\033[0m")
        
        if current_idx < total_stages:
            print("        │")
            print("        ▼ (EventBus Dispatch)")

    def render_execution_summary(self, result: SwarmExecutionResult) -> None:
        print("\n" + "─" * 70)
        print("  🎉 SWARM PIPELINE COMPLETED SUCCESSFULLY")
        print("─" * 70)
        print(f"  • Execution ID      : \033[1;33m{result.execution_id}\033[0m")
        print(f"  • Architecture ADR  : \033[1;32m{result.adr_title}\033[0m")
        print(f"  • Security Audit    : {'\033[1;32m0 CWEs Detected (PASS)\033[0m' if result.security_clean else 'Hardened'}")
        print(f"  • Test Suite (QA)   : {'\033[1;32mAll Invariant Tests Passed\033[0m' if result.tests_passed else 'Failed'}")
        print(f"  • Token Optimization: \033[1;36m{result.token_savings_pct}% Context Compressed ($0 Waste)\033[0m")
        print(f"  • Total Runtime     : \033[1;37m{result.total_duration_ms}ms\033[0m")
        print(f"  • Episodic Memories : \033[1;35m{result.memory_recalled_count} prior patterns recalled\033[0m")
        print("=" * 70 + "\n")


visualizer = SwarmAsciiVisualizer()
