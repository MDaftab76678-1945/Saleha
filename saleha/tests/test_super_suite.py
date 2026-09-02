"""Unit and Integration Test Suite for Saleha Sovereign Super-Suite (Advanced Kimi Feature Matrix)."""

import pytest
from unittest.mock import MagicMock

from saleha.agents.deep_researcher import DeepResearcherAgent, deep_researcher
from saleha.agents.slides_architect import SlidesArchitectAgent, slides_architect
from saleha.agents.sheets_analyst import SheetsAnalystAgent, sheets_analyst
from saleha.agents.browser_claw import SovereignClawAgent, browser_claw
from saleha.core.task_scheduler import TaskSchedulerEngine, task_scheduler
from saleha.cli.chat_session import SwarmChatSession


class TestDeepResearcherAgent:
    def test_execute_agent_response(self):
        agent = DeepResearcherAgent()
        res = agent.execute("Distributed consensus in blockchain")
        assert res.success is True
        assert "Key Empirical Findings" in res.content
        assert res.tokens_used > 0

    def test_conduct_research_structure(self):
        report = deep_researcher.conduct_research("Vector databases and ANN indexing")
        assert report.topic == "Vector databases and ANN indexing"
        assert len(report.citations) >= 3
        assert len(report.key_findings) >= 4
        assert "Verified Citations" in report.full_markdown_report
        assert report.generation_time_ms >= 0


class TestSlidesArchitectAgent:
    def test_execute_agent_response(self):
        agent = SlidesArchitectAgent()
        res = agent.execute("High throughput ring buffer")
        assert res.success is True
        assert "marp: true" in res.content

    def test_synthesize_deck(self):
        deck = slides_architect.synthesize_deck("Microservices Hexagonal Architecture")
        assert len(deck.slides) == 4
        assert "marp: true" in deck.marp_markdown
        assert "<!DOCTYPE html>" in deck.html5_presentation
        assert deck.slides[1].mermaid_diagram is not None


class TestSheetsAnalystAgent:
    def test_execute_agent_response(self):
        agent = SheetsAnalystAgent()
        res = agent.execute("Monthly API token usage and cost")
        assert res.success is True
        assert "Tabular Analysis" in res.content
        assert "SELECT" in res.content

    def test_analyze_tabular_query(self):
        res = sheets_analyst.analyze_tabular_query("Latency and Memory Spike Telemetry")
        assert res.total_rows == 10000
        assert len(res.columns) == 5
        assert len(res.anomalies) >= 1
        assert "APPROX_QUANTILES" in res.synthesized_sql_query
        assert "Bucket Hour" in res.ascii_table_preview


class TestSovereignClawAgent:
    def test_execute_agent_response(self):
        agent = SovereignClawAgent()
        res = agent.execute("https://docs.saleha.ai")
        assert res.success is True
        assert "Sovereign Claw Navigation Result" in res.content

    def test_crawl_and_extract(self):
        res = browser_claw.crawl_and_extract("https://github.com/MDaftab76678-1945/Saleha")
        assert res.http_status == 200
        assert res.dom_elements_scanned >= 1000
        assert len(res.action_trace) == 3
        assert "metrics" in res.extracted_data


class TestTaskSchedulerEngine:
    def test_register_and_list_tasks(self):
        engine = TaskSchedulerEngine()
        initial_count = len(engine.list_tasks())
        task = engine.register_task("0 0 * * *", "Daily AST Hygiene Audit", "RefactorSpecialistAgent")
        assert task.task_id.startswith("task_")
        assert task.cron_expression == "0 0 * * *"
        assert len(engine.list_tasks()) == initial_count + 1

    def test_trigger_and_cancel_task(self):
        engine = TaskSchedulerEngine()
        task = engine.register_task("*/10 * * * *", "Health Check", "TesterAgent")
        result = engine.trigger_task_now(task.task_id)
        assert result is not None
        assert result["status"] == "SUCCESS"
        assert task.total_executions == 1

        assert engine.cancel_task(task.task_id) is True
        assert engine.get_task(task.task_id) is None


class TestSwarmChatSessionSuperSuiteCommands:
    def test_super_suite_slash_commands(self):
        mock_console = MagicMock()
        session = SwarmChatSession(console=mock_console)

        assert session.process_command("/research High Performance Computing") is True
        assert session.process_command("/slides Zero-Copy Serialization") is True
        assert session.process_command("/sheet P99 Latency Telemetry") is True
        assert session.process_command("/claw https://saleha.ai") is True
        assert session.process_command("/schedule 0 * * * * Auto Audit") is True
        assert session.process_command("/tasks") is True
