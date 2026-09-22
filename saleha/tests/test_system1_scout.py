"""
Tests for System-1 AST Scout & Call-Chain Localizer (Zero-Token Pre-flight Reconnaissance).

Verifies:
1. Candidate symbol extraction from goals and tracebacks.
2. Primary symbol definition & exact line range localization.
3. Multi-hop callee helper resolution (the Pass 106 one-level-shallow defect fix).
4. Workspace test file association.
5. Integration with AgentLoop (pre-seeding confirmed_files, located_region, and prompt).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from typing import Any, Optional

from saleha.agents.base_agent import AgentResponse
from saleha.core.graph.system1_scout import ScoutDossier, SymbolDossier, System1Scout
from saleha.core.loop.agentic_loop import AgentLoop


class ScriptedAgent:
    """Deterministic mock agent for testing AgentLoop integration."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def think(
        self,
        prompt: str,
        previous_error_reflexion: Optional[str] = None,
        complexity_score: float = 0.0,
        disable_reasoning: bool = False,
        **kwargs: Any,
    ) -> AgentResponse:
        self.prompts.append(prompt)
        if not self.responses:
            return AgentResponse(success=False, content="", error_message="No more scripted responses")
        content = self.responses.pop(0)
        return AgentResponse(success=True, content=content)



class TestSystem1Scout(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_extract_candidates_filters_noise(self) -> None:
        scout = System1Scout(self.root)
        goal = "Fix the bug in super_len when called with None in requests.compat"
        candidates = scout.extract_candidates(goal)
        self.assertIn("super_len", candidates)
        self.assertIn("requests", candidates)
        self.assertIn("compat", candidates)
        self.assertNotIn("the", candidates)
        self.assertNotIn("bug", candidates)
        self.assertNotIn("when", candidates)
        self.assertNotIn("with", candidates)

    def test_scout_primary_symbol_localization(self) -> None:
        # Create a module with a function
        utils_py = os.path.join(self.root, "utils.py")
        with open(utils_py, "w", encoding="utf-8") as f:
            f.write(
                "# Header comments\n"
                "def super_len(o):\n"
                '    """Calculate length of object."""\n'
                "    if o is None:\n"
                "        return 0\n"
                "    return len(o)\n"
            )

        scout = System1Scout(self.root)
        dossier: ScoutDossier = scout.scout("Fix bug in super_len")

        self.assertTrue(dossier.has_matches)
        self.assertEqual(len(dossier.primary_symbols), 1)
        sym: SymbolDossier = dossier.primary_symbols[0]
        self.assertEqual(sym.name, "super_len")
        self.assertEqual(sym.file_path, "utils.py")
        self.assertEqual(sym.start_line, 2)
        self.assertEqual(sym.end_line, 6)
        self.assertIn("def super_len", sym.code_slice)
        self.assertEqual(dossier.primary_region, ("utils.py", 2, 6))
        self.assertIn("utils.py", dossier.relevant_files)

    def test_scout_callee_resolution_pass106_gap(self) -> None:
        """
        Simulates the Pass 106 SWE-bench requests-3362 failure mode:
        Top-level caller: super_len in utils.py
        Callee helper: _get_size in compat.py
        Verifies Scout locates BOTH caller and callee helper definitions.
        """
        os.makedirs(os.path.join(self.root, "src"), exist_ok=True)
        utils_path = os.path.join(self.root, "src", "utils.py")
        compat_path = os.path.join(self.root, "src", "compat.py")

        with open(compat_path, "w", encoding="utf-8") as f:
            f.write(
                "def _get_size(stream):\n"
                "    if hasattr(stream, 'len'):\n"
                "        return stream.len\n"
                "    return 0\n"
            )

        with open(utils_path, "w", encoding="utf-8") as f:
            f.write(
                "from src.compat import _get_size\n\n"
                "def super_len(o):\n"
                "    total = _get_size(o)\n"
                "    return total\n"
            )

        scout = System1Scout(self.root)
        dossier = scout.scout("Resolve defect in super_len calculation")

        self.assertTrue(dossier.has_matches)
        # Primary symbol
        prim_names = [s.name for s in dossier.primary_symbols]
        self.assertIn("super_len", prim_names)

        # Callee helper symbol
        callee_names = [c.name for c in dossier.callee_symbols]
        self.assertIn("_get_size", callee_names)

        callee = next(c for c in dossier.callee_symbols if c.name == "_get_size")
        self.assertEqual(callee.file_path.replace("\\", "/"), "src/compat.py")
        self.assertEqual(callee.start_line, 1)
        self.assertEqual(callee.end_line, 4)
        self.assertIn("def _get_size", callee.code_slice)

        # Both files confirmed
        norm_relevant = {f.replace("\\", "/") for f in dossier.relevant_files}
        self.assertIn("src/utils.py", norm_relevant)
        self.assertIn("src/compat.py", norm_relevant)

    def test_scout_associated_test_files(self) -> None:
        os.makedirs(os.path.join(self.root, "tests"), exist_ok=True)
        src_file = os.path.join(self.root, "service.py")
        test_file = os.path.join(self.root, "tests", "test_service.py")

        with open(src_file, "w", encoding="utf-8") as f:
            f.write("def authenticate_user(token):\n    return token == 'valid'\n")

        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                "from service import authenticate_user\n\n"
                "def test_auth():\n"
                "    assert authenticate_user('valid') is True\n"
            )

        scout = System1Scout(self.root)
        dossier = scout.scout("fix bug in authenticate_user")

        self.assertTrue(dossier.has_matches)
        norm_tests = [t.replace("\\", "/") for t in dossier.test_files]
        self.assertIn("tests/test_service.py", norm_tests)

    def test_format_briefing_structure(self) -> None:
        sym = SymbolDossier(
            name="process_payment",
            kind="function",
            file_path="billing/payment.py",
            start_line=10,
            end_line=25,
            code_slice="10: def process_payment():\n11:     pass",
            callees=["verify_card"],
        )
        callee = SymbolDossier(
            name="verify_card",
            kind="function",
            file_path="billing/cards.py",
            start_line=50,
            end_line=65,
            code_slice="50: def verify_card():\n51:     pass",
        )
        dossier = ScoutDossier(
            query="fix process_payment",
            primary_symbols=[sym],
            callee_symbols=[callee],
            relevant_files={"billing/payment.py", "billing/cards.py"},
            test_files=["tests/test_payment.py"],
            primary_region=("billing/payment.py", 10, 25),
        )

        briefing = dossier.format_briefing()
        self.assertIn("[System-1 Scout Localization]", briefing)
        self.assertIn("Target Symbol: `process_payment` in `billing/payment.py`", briefing)
        self.assertIn("Callees (Helpers called inside target): `verify_card`", briefing)
        self.assertIn("Associated Tests: `tests/test_payment.py`", briefing)
        self.assertIn("--- billing/payment.py", briefing)
        self.assertIn("--- billing/cards.py", briefing)

    def test_agent_loop_scout_integration(self) -> None:
        """Verifies AgentLoop automatically runs Scout, seeds confirmed_files & located_region."""
        app_file = os.path.join(self.root, "app.py")
        with open(app_file, "w", encoding="utf-8") as f:
            f.write("def compute_tax(income):\n    return income * 0.2\n")

        agent = ScriptedAgent([
            '```tool_call\n{"tool": "read_file", "args": {"path": "app.py", "start_line": 1, "end_line": 2}}\n```',
            '```json\n{"finish": "tax computed"}\n```',
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root, enable_scout=True)
        res = loop.run("Fix issue in compute_tax calculation")

        self.assertTrue(res.success, res.error)
        self.assertEqual(res.final_message, "tax computed")
        # Step 0 is not in res.steps (res.steps records LLM turns)
        self.assertEqual(res.steps[0].action, "read_file")

        # Verify scout dossier was created and populated
        self.assertIsNotNone(loop.scout_dossier)
        self.assertTrue(loop.scout_dossier.has_matches)
        self.assertEqual(loop.scout_dossier.primary_symbols[0].name, "compute_tax")

        # Verify prompt contained scout intelligence
        self.assertIn("## System-1 Static Intelligence", agent.prompts[0])
        self.assertIn("[System-1 Scout Localization]", agent.prompts[0])
        self.assertIn("compute_tax", agent.prompts[0])

    def test_agent_loop_scout_symbols_tool(self) -> None:
        """Verifies model can call scout_symbols as a tool during loop execution."""
        app_file = os.path.join(self.root, "crypto.py")
        with open(app_file, "w", encoding="utf-8") as f:
            f.write("def hash_password(pw):\n    return pw + '_hash'\n")

        agent = ScriptedAgent([
            '```tool_call\n{"tool": "scout_symbols", "args": {"query": "hash_password"}}\n```',
            '```json\n{"finish": "scout completed"}\n```',
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root, enable_scout=True)
        res = loop.run("investigate security")

        self.assertTrue(res.success, res.error)
        self.assertEqual(res.steps[0].action, "scout_symbols")
        self.assertIn("[System-1 Scout Localization]", res.steps[0].observation)
        self.assertIn("hash_password", res.steps[0].observation)

    def test_scout_two_letter_identifier_and_empty_inputs(self) -> None:
        """Verifies 2-letter symbols (e.g., db) are captured and empty inputs handled safely."""
        scout = System1Scout(self.root)
        self.assertEqual(scout.extract_candidates(""), [])
        self.assertEqual(scout.extract_candidates("   "), [])
        
        candidates = scout.extract_candidates("query db and check status of io")
        self.assertIn("db", candidates)
        self.assertIn("io", candidates)
        self.assertNotIn("of", candidates)
        self.assertNotIn("and", candidates)

        dossier = scout.scout("")
        self.assertFalse(dossier.has_matches)
        self.assertEqual(dossier.format_briefing(), "")


if __name__ == "__main__":
    unittest.main()
