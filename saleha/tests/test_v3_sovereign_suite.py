"""Unit and Integration Test Suite for Saleha v3.0.0 Sovereign Suite."""

import pytest
from unittest.mock import MagicMock

from saleha.core.local_inference_engine import (
    LocalInferenceEngine,
    LocalInferenceResult,
    local_inference_engine,
)
from saleha.core.repo_orchestrator import (
    AutonomousRepoOrchestrator,
    AutoPRResult,
    repo_orchestrator,
)
from saleha.agents.voice_architect import (
    VoiceArchitectAgent,
    VoiceCommentaryResult,
    voice_architect,
)
from saleha.cli.chat_session import SwarmChatSession


class TestLocalInferenceEngine:
    def test_generate_code_prompt(self):
        engine = LocalInferenceEngine()
        res = engine.generate("def add(a: int, b: int) -> int:")
        assert "def execute_sovereign_task" in res.text
        assert res.tokens_generated > 0
        assert res.duration_ms >= 0

    def test_list_and_set_model(self):
        engine = LocalInferenceEngine()
        models = engine.list_available_models()
        assert "qwen2.5-coder:1.5b" in models
        assert engine.set_active_model("deepseek-r1:1.5b") is True
        assert engine.active_model == "deepseek-r1:1.5b"

    def test_stream_tokens(self):
        engine = LocalInferenceEngine()
        tokens = list(engine.stream_tokens("hello"))
        assert len(tokens) > 0


class TestAutonomousRepoOrchestrator:
    def test_execute_auto_pr(self):
        orchestrator = AutonomousRepoOrchestrator()
        result = orchestrator.execute_auto_pr("Implement Distributed Rate Limiter with Redis")
        assert "feat/saleha-implement-distributed-rate-limite" in result.branch_name
        assert "feat: Implement Distributed Rate Limiter with Redis" in result.pr_title
        assert result.tests_passed is True
        assert "Pull Request" in result.pr_markdown_body
        assert len(result.files_modified) == 2


class TestVoiceArchitectAgent:
    def test_voice_agent_execution(self):
        agent = VoiceArchitectAgent()
        res = agent.execute("Microservices Hexagonal ADR")
        assert res.success is True
        assert "VoiceArchitectAgent" in res.content
        assert "Verbal Audio Transcript" in res.content

    def test_synthesize_voice_commentary(self):
        result = voice_architect.synthesize_voice_commentary("Kafka EventBus Consumer")
        assert result.audio_duration_estimate_sec > 0
        assert "hexagonal boundaries" in result.transcript
        assert len(result.bullet_talking_points) >= 3


class TestSwarmChatSessionV3Commands:
    def test_process_v3_commands(self):
        mock_console = MagicMock()
        session = SwarmChatSession(console=mock_console)
        assert session.process_command("/auto-pr Distributed Lock with Redis") is True
        assert session.process_command("/voice Explain Cache Aside Pattern") is True
        assert session.process_command("/local-model qwen2.5-coder:7b") is True
