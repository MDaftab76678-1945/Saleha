"""
Market-upgrade regression tests:
- SmartRouter 2026 catalog + runtime probing
- HybridGateway Anthropic/Gemini native dispatch
- Dynamic-import static detection (__import__ / importlib.import_module)
- ExecutionPolicy (sandbox modes + Docker command builder)
- Reviewer fail-closed posture
- web_fetch SSRF guard
- Complexity score wiring (Planner -> Coder -> router)
"""
from __future__ import annotations

import os
import unittest
from typing import Any, Dict, List, Tuple
from unittest.mock import patch, MagicMock

from saleha.core.platform.smart_router import (
    SmartRouter,
    get_default_history_path,
    get_installed_ollama_models,
)
from saleha.core.hybrid_gateway import HybridModelGateway
from saleha.core.safety_patterns import _check_blocked_imports as sp_check_imports
from saleha.core.harness.code_executor import CodeExecutor, ExecutionResult, _check_blocked_imports
from saleha.core.execution_policy import (
    build_docker_command,
    get_sandbox_mode,
    resolve_backend,
    docker_available,
    _reset_probe_cache,
)


class SmartRouter2026Tests(unittest.TestCase):
    def test_new_catalog_models_present(self) -> None:
        router = SmartRouter(history_file=os.devnull)
        for model in ("qwen3-coder:30b", "devstral:24b", "deepseek-r1:8b",
                      "qwen2.5-coder:7b", "qwen3:4b"):
            self.assertIn(model, router.models)

    def test_default_history_path_under_home_saleha(self) -> None:
        path = get_default_history_path()
        expected_tail = os.path.join(".saleha", "router_history.json")
        self.assertTrue(path.endswith(expected_tail), path)

    def test_probe_filters_candidates_to_installed_models(self) -> None:
        router = SmartRouter(history_file=os.devnull, probe_runtime=True)
        with patch("saleha.core.platform.smart_router.get_installed_ollama_models",
                   return_value={"qwen2.5-coder:7b"}):
            candidates = router._filter_installed(
                ["devstral:24b", "deepseek-coder:6.7b", "qwen2.5-coder:7b", "qwen2.5-coder:3b"]
            )
        self.assertEqual(candidates, ["qwen2.5-coder:7b"])

    def test_probe_failure_falls_back_to_static_candidates(self) -> None:
        router = SmartRouter(history_file=os.devnull, probe_runtime=True)
        original = ["devstral:24b", "deepseek-coder:6.7b"]
        with patch("saleha.core.platform.smart_router.get_installed_ollama_models", return_value=set()):
            self.assertEqual(router._filter_installed(original), original)

    def test_select_model_with_probe_picks_installed_flagship(self) -> None:
        router = SmartRouter(history_file=os.devnull, probe_runtime=True)
        with patch("saleha.core.platform.smart_router.get_installed_ollama_models",
                   return_value={"qwen3-coder:30b", "deepseek-r1:8b"}):
            selected = router.select_model(
                "design a distributed system architecture", complexity_score=9.5
            )
        self.assertEqual(selected, "qwen3-coder:30b")


def _make_cm(payload: Dict[str, Any]) -> Any:
    """Build a side_effect for urllib.request.urlopen returning a CM response."""
    import json as _json

    class _Resp:
        status = 200

        def read(self) -> bytes:
            return _json.dumps(payload).encode("utf-8")

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *exc: Any) -> bool:
            return False

    return lambda *a, **k: _Resp()


class GatewayNativeProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gateway = HybridModelGateway()

    def test_anthropic_dispatch_native_api(self) -> None:
        payload = {
            "content": [{"type": "text", "text": "claude says hi"}],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
        with patch("urllib.request.urlopen", side_effect=_make_cm(payload)), \
             patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            res = self.gateway.generate("hello", provider="anthropic")
        self.assertTrue(res.success, res.error)
        self.assertEqual(res.provider, "anthropic")
        self.assertIn("claude says hi", res.content)
        self.assertEqual(res.tokens_used, 30)

    def test_gemini_dispatch_native_api(self) -> None:
        payload = {
            "candidates": [{"content": {"parts": [{"text": "gemini says hi"}]}}],
            "usageMetadata": {"totalTokenCount": 55},
        }
        with patch("urllib.request.urlopen", side_effect=_make_cm(payload)), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "g-key"}):
            res = self.gateway.generate("hello", provider="gemini")
        self.assertTrue(res.success, res.error)
        self.assertEqual(res.provider, "gemini")
        self.assertIn("gemini says hi", res.content)
        self.assertEqual(res.tokens_used, 55)

    def test_anthropic_missing_key_fails_gracefully(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            res = self.gateway.generate("x", provider="anthropic")
        self.assertFalse(res.success)
        self.assertIn("missing", res.error.lower())


class DynamicImportDetectionTests(unittest.TestCase):
    def test_dunder_import_constant_blocked(self) -> None:
        self.assertIsNotNone(_check_blocked_imports('getattr(__import__("shutil"), "rmtree")("/")'))

    def test_importlib_import_module_blocked(self) -> None:
        self.assertIsNotNone(sp_check_imports("import importlib\nimportlib.import_module('os')"))

    def test_importlib_kwarg_form_blocked(self) -> None:
        self.assertIsNotNone(sp_check_imports("from importlib import import_module\nimport_module(name='sqlite3')"))

    def test_non_literal_dynamic_import_not_false_positives(self) -> None:
        # Non-literal argument, statically unknown -> not flagged here
        # (that is the runtime sandbox layer's responsibility).
        self.assertIsNone(sp_check_imports("mod = 'os'\n__import__(mod)"))

    def test_plain_code_still_allowed(self) -> None:
        self.assertIsNone(_check_blocked_imports("import math\nprint(math.sqrt(4))"))


class ExecutionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset_probe_cache()
        os.environ.pop("SALEHA_SANDBOX", None)

    def tearDown(self) -> None:
        _reset_probe_cache()
        os.environ.pop("SALEHA_SANDBOX", None)

    def test_mode_aliases_and_invalid_values(self) -> None:
        cases = {
            None: "auto",
            "auto": "auto",
            "local": "local",
            "subprocess": "local",
            "docker": "docker",
            "strict": "require-docker",
            "garbage": "auto",
        }
        for raw, expected in cases.items():
            if raw is None:
                os.environ.pop("SALEHA_SANDBOX", None)
            else:
                os.environ["SALEHA_SANDBOX"] = raw
            self.assertEqual(get_sandbox_mode(), expected, raw)

    def test_require_docker_fail_closed_when_no_daemon(self) -> None:
        os.environ["SALEHA_SANDBOX"] = "require-docker"
        with patch("saleha.core.execution_policy.docker_available", return_value=False):
            backend, reason = resolve_backend()
        self.assertEqual(backend, "none")
        self.assertIn("fail-closed", reason.lower())

    def test_docker_mode_degrades_with_warning_reason(self) -> None:
        os.environ["SALEHA_SANDBOX"] = "docker"
        with patch("saleha.core.execution_policy.docker_available", return_value=False):
            backend, reason = resolve_backend()
        self.assertEqual(backend, "subprocess")
        self.assertIn("degraded", reason.lower())

    def test_docker_command_is_hardened(self) -> None:
        # POSIX-style path -- Linux CI has no backslash basename to worry about.
        cmd = build_docker_command("/tmp/work/script.py")
        joined = " ".join(cmd)
        self.assertIn("--network none", joined)
        self.assertIn("--memory", joined)
        self.assertIn("--pids-limit 128", joined)
        self.assertIn("no-new-privileges", joined)
        self.assertTrue(cmd[-2:] == ["python", "/sandbox/script.py"])

    def test_executor_refuses_execution_in_strict_mode_without_daemon(self) -> None:
        os.environ["SALEHA_SANDBOX"] = "require-docker"
        try:
            with patch("saleha.core.execution_policy.docker_available", return_value=False):
                result = CodeExecutor(timeout=5, audit=False).execute("print('hi')")
            self.assertFalse(result.success)
            self.assertTrue(result.blocked)
            self.assertEqual(result.backend, "none")
        finally:
            os.environ.pop("SALEHA_SANDBOX", None)

    def test_executor_reports_subprocess_backend_by_default(self) -> None:
        result = CodeExecutor(timeout=5, audit=False).execute("print('backend_ok')")
        self.assertTrue(result.success)
        self.assertEqual(result.backend, "subprocess")

    def test_delegated_import_check_matches_core(self) -> None:
        self.assertEqual(
            _check_blocked_imports("import socket"),
            sp_check_imports("import socket"),
        )


class ReviewerFailClosedTests(unittest.TestCase):
    def test_llm_failure_blocks_approval_by_default(self) -> None:
        from saleha.agents.reviewer import ReviewerAgent

        reviewer = ReviewerAgent(model="test-model")
        fake_response = MagicMock(success=False, content="", error_message="Ollama down",
                                  model_used="test-model")
        with patch.object(reviewer, "think", return_value=fake_response), \
             patch.dict(os.environ, {}):
            os.environ.pop("SALEHA_REVIEW_OFFLINE_PASS", None)
            result = reviewer.review_code("task", "print(1)")
        self.assertFalse(result.approved)
        self.assertIn("failing closed", result.feedback.lower())

    def test_offline_escape_hatch_restores_legacy_behavior(self) -> None:
        from saleha.agents.reviewer import ReviewerAgent

        reviewer = ReviewerAgent(model="test-model")
        fake_response = MagicMock(success=False, content="", error_message="Ollama down",
                                  model_used="test-model")
        with patch.object(reviewer, "think", return_value=fake_response), \
             patch.dict(os.environ, {"SALEHA_REVIEW_OFFLINE_PASS": "1"}):
            result = reviewer.review_code("task", "print(1)")
        self.assertTrue(result.approved)


class WebFetchGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        from saleha.core.tool_calling import global_tool_registry
        self.registry = global_tool_registry

    def test_file_scheme_rejected(self) -> None:
        res = self.registry.execute("web_fetch", url="file:///etc/passwd")
        self.assertFalse(res.success)
        self.assertIn("scheme", res.error.lower())

    def test_localhost_rejected(self) -> None:
        res = self.registry.execute("web_fetch", url="http://localhost:11434/api/tags")
        self.assertFalse(res.success)
        self.assertIn("internal host", res.error.lower())

    def test_private_resolved_ip_rejected(self) -> None:
        fake_info: List[Tuple[Any, Any, Any, str, Tuple[str, int]]] = [
            (None, None, None, "", ("192.168.1.10", 0))
        ]
        with patch("socket.getaddrinfo", return_value=fake_info):
            res = self.registry.execute("web_fetch", url="https://intranet.example.com/x")
        self.assertFalse(res.success)
        self.assertIn("non-public", res.error.lower())

    def test_unresolvable_host_rejected_cleanly(self) -> None:
        with patch("socket.getaddrinfo", side_effect=OSError("no dns")):
            res = self.registry.execute("web_fetch", url="https://nonexistent.invalid/x")
        self.assertFalse(res.success)
        self.assertIn("resolve", res.error.lower())


class ComplexityWiringTests(unittest.TestCase):
    def test_plan_result_carries_complexity_score(self) -> None:
        from saleha.agents.planner import PlanResult

        pr = PlanResult(success=True, steps=["step"], recommendation="OK",
                        raw_response="", complexity_score=7.5)
        self.assertEqual(pr.complexity_score, 7.5)
        # default backward-compatible
        pr_default = PlanResult(success=True, steps=[], recommendation="OK")
        self.assertEqual(pr_default.complexity_score, 0.0)

    def test_coder_forwards_complexity_to_router(self) -> None:
        from saleha.agents.coder import CoderAgent

        coder = CoderAgent(model="fixed-model")
        seen: Dict[str, float] = {}

        def fake_think(prompt: str, previous_error_reflexion: Any = None,
                       complexity_score: float = 0.0) -> MagicMock:
            seen["complexity"] = complexity_score
            return MagicMock(success=True, content="```python\nprint(1)\n```",
                             error_message="", model_used="m")

        with patch.object(coder, "think", side_effect=fake_think):
            res = coder.generate_code("do it", complexity_score=6.5)

        self.assertTrue(res.success)
        self.assertEqual(seen["complexity"], 6.5)


class ProfileRoleRoutingTests(unittest.TestCase):
    """v1.4: llm_routing metadata now has a real routing/temperature effect."""

    def test_role_complexity_floors(self) -> None:
        from saleha.core.agent_profile_loader import profile_registry, ProfileAgent

        sec = ProfileAgent(profile=profile_registry.get("agent_security_engineer"), model="m")
        self.assertGreaterEqual(sec.complexity_floor, 8.0)
        sde = ProfileAgent(profile=profile_registry.get("agent_sde"), model="m")
        self.assertGreaterEqual(sde.complexity_floor, 6.0)
        qa = ProfileAgent(profile=profile_registry.get("agent_test_automation_engineer"), model="m")
        self.assertLessEqual(qa.complexity_floor, 3.0)

    def test_temperature_from_llm_routing_flows_to_provider(self) -> None:
        from saleha.agents.base_agent import BaseAgent
        agent = BaseAgent(role="T", model="fixed-model")
        agent.temperature = 0.15
        captured: Dict[str, Any] = {}

        def fake_generate(model: str, prompt: str, options: Any = None,
                         response_format: Any = None,
                         disable_reasoning: bool = False) -> MagicMock:
            captured["options"] = options
            return MagicMock(success=True, content="ok", error_message="", response_time=0.01, tokens_used=3)

        with patch.object(agent.provider, "generate", side_effect=fake_generate):
            resp = agent.think("hello")
        self.assertTrue(resp.success)
        self.assertEqual(captured["options"], {"temperature": 0.15})

    def test_sde_profile_reads_routing_temperature(self) -> None:
        from saleha.core.agent_profile_loader import profile_registry, ProfileAgent

        sde = profile_registry.get("agent_sde")
        if not (sde.llm_routing and sde.llm_routing.get("temperature")):
            self.skipTest("profile file lacks temperature metadata")
        agent = ProfileAgent(profile=sde, model="m")
        self.assertIsNotNone(agent.temperature)
        self.assertLessEqual(agent.temperature, 0.9)


if __name__ == "__main__":
    unittest.main()
