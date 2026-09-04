"""
Unit and integration tests for Saleha Soul Engine & SoulSpec v1.0 CLI.
"""

import unittest
from click.testing import CliRunner
from saleha.core.soul_engine import SoulEngine, soul_engine
from saleha.cli.soul_cli import soul_group


class TestSoulEngine(unittest.TestCase):
    """Test discovery, loading, switching, and integrity of SoulSpec packages."""

    def test_ten_souls_registered(self):
        souls = soul_engine.list_souls()
        names = [s.name for s in souls]
        self.assertEqual(len(souls), 10)
        expected = [
            "alchemist", "architect", "artisan", "auditor", "minimalist",
            "sage", "sentinel", "sovereign", "speedrunner", "sre"
        ]
        for exp in expected:
            self.assertIn(exp, names)

    def test_soul_package_integrity(self):
        sovereign = soul_engine.get_soul("sovereign")
        self.assertIsNotNone(sovereign)
        self.assertEqual(sovereign.name, "sovereign")
        self.assertIn("Swarm Commander", sovereign.archetype)
        self.assertTrue(len(sovereign.soul_md) > 100)
        self.assertTrue(len(sovereign.identity_md) > 50)
        self.assertTrue(len(sovereign.style_md) > 50)
        self.assertIn("consensus", sovereign.tags)

    def test_render_system_prompt(self):
        architect = soul_engine.get_soul("architect")
        self.assertIsNotNone(architect)
        prompt = architect.render_system_prompt()
        self.assertIn("Active Persona: Principal Systems Architect", prompt)
        self.assertIn("Domain-Driven Boundaries", prompt)
        self.assertIn("Communication Style", prompt)

    def test_active_soul_switching(self):
        prev = soul_engine.get_active_soul_name()
        try:
            # Switch to sentinel
            sec = soul_engine.set_active_soul("sentinel")
            self.assertEqual(sec.name, "sentinel")
            self.assertEqual(soul_engine.get_active_soul_name(), "sentinel")
            active_obj = soul_engine.get_active_soul()
            self.assertEqual(active_obj.name, "sentinel")
        finally:
            # Revert to original
            soul_engine.set_active_soul(prev)

    def test_unknown_soul_raises_keyerror(self):
        with self.assertRaises(KeyError):
            soul_engine.set_active_soul("nonexistent_ultra_mythical_soul")

    def test_validation_clean(self):
        report = soul_engine.validate_all()
        self.assertEqual(report["invalid_souls"], 0)
        self.assertEqual(report["valid_souls"], 10)
        self.assertEqual(len(report["errors"]), 0)


class TestSoulCLI(unittest.TestCase):
    """Test Click CLI command suite for souls."""

    def setUp(self):
        self.runner = CliRunner()

    def test_cli_soul_list(self):
        result = self.runner.invoke(soul_group, ["list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Saleha Cognitive Personas (SoulSpec v1.0)", result.output)
        self.assertIn("sovereign", result.output)
        self.assertIn("architect", result.output)
        self.assertIn("sentinel", result.output)

    def test_cli_soul_use(self):
        result = self.runner.invoke(soul_group, ["use", "speedrunner"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Soul Transition Complete", result.output)
        self.assertIn("Speedrunner", result.output)

        # Revert back to sovereign
        rev = self.runner.invoke(soul_group, ["use", "sovereign"])
        self.assertEqual(rev.exit_code, 0)

    def test_cli_soul_show(self):
        result = self.runner.invoke(soul_group, ["show", "auditor"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Formal Verification Auditor", result.output)
        self.assertIn("Lean 4", result.output)

    def test_cli_soul_validate(self):
        result = self.runner.invoke(soul_group, ["validate"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All 10 SoulSpec personas are 100% valid and verified", result.output)


if __name__ == "__main__":
    unittest.main()
