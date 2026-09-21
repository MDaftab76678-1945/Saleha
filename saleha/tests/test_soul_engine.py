"""
Unit and integration tests for Saleha Soul Engine & SoulSpec v1.0 CLI.
"""

import os
import tempfile
import unittest
from click.testing import CliRunner
from saleha.core.soul_engine import SoulEngine, soul_engine
from saleha.cli.soul_cli import soul_group


class TestSoulEngine(unittest.TestCase):
    """Test discovery, loading, switching, and integrity of SoulSpec packages."""

    def test_ten_souls_registered(self) -> None:
        souls = soul_engine.list_souls()
        names = [s.name for s in souls]
        self.assertEqual(len(souls), 10)
        expected = [
            "alchemist", "architect", "artisan", "auditor", "minimalist",
            "sage", "sentinel", "sovereign", "speedrunner", "sre"
        ]
        for exp in expected:
            self.assertIn(exp, names)

    def test_soul_package_integrity(self) -> None:
        sovereign = soul_engine.get_soul("sovereign")
        self.assertIsNotNone(sovereign)
        self.assertEqual(sovereign.name, "sovereign")
        self.assertIn("Swarm Commander", sovereign.archetype)
        self.assertTrue(len(sovereign.soul_md) > 100)
        self.assertTrue(len(sovereign.identity_md) > 50)
        self.assertTrue(len(sovereign.style_md) > 50)
        self.assertIn("consensus", sovereign.tags)

    def test_render_system_prompt(self) -> None:
        architect = soul_engine.get_soul("architect")
        self.assertIsNotNone(architect)
        prompt = architect.render_system_prompt()
        self.assertIn("Active Persona: Principal Systems Architect", prompt)
        self.assertIn("Domain-Driven Boundaries", prompt)
        self.assertIn("Communication Style", prompt)

    def test_active_soul_switching(self) -> None:
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

    def test_unknown_soul_raises_keyerror(self) -> None:
        with self.assertRaises(KeyError):
            soul_engine.set_active_soul("nonexistent_ultra_mythical_soul")

    def test_validation_clean(self) -> None:
        report = soul_engine.validate_all()
        self.assertEqual(report["invalid_souls"], 0)
        self.assertEqual(report["valid_souls"], 10)
        self.assertEqual(len(report["errors"]), 0)

    def _make_two_soul_engine(self, souls_dir: str, config_dir: str) -> SoulEngine:
        for name in ("alpha_soul", "beta_soul"):
            d = os.path.join(souls_dir, name)
            os.makedirs(d)
            with open(os.path.join(d, "soul.json"), "w", encoding="utf-8") as f:
                f.write(f'{{"name": "{name}", "displayName": "{name}", "archetype": "General"}}')
            with open(os.path.join(d, "SOUL.md"), "w", encoding="utf-8") as f:
                f.write("x" * 60)
        return SoulEngine(souls_dir=souls_dir, config_dir=config_dir)

    def test_set_active_soul_raises_when_persist_fails(self) -> None:
        """Real bug found auditing this module: set_active_soul() swallowed
        any write failure with a bare `except Exception: pass` and still
        returned the requested soul, so a caller believed the switch had
        succeeded while get_active_soul_name() -- which re-reads the same
        file -- kept reporting a stale, different soul on every later call.
        Confirmed by direct probe with two real souls before fixing: the
        return value said "beta_soul" while the actual persisted/effective
        active soul stayed "alpha_soul". Must now raise instead of lying."""
        with tempfile.TemporaryDirectory() as souls_dir, \
             tempfile.TemporaryDirectory() as config_dir:
            engine = self._make_two_soul_engine(souls_dir, config_dir)
            # Force the persist write to fail by pointing at a path that
            # cannot be opened for writing (a directory, not a file).
            bad_path = engine._active_file
            os.makedirs(bad_path, exist_ok=True)
            with self.assertRaises(OSError):
                engine.set_active_soul("beta_soul")

    def test_reload_reports_skipped_souls_instead_of_silence(self) -> None:
        """A broken soul package must be reported, not silently skipped."""
        with tempfile.TemporaryDirectory() as souls_dir, \
             tempfile.TemporaryDirectory() as config_dir:
            good_dir = os.path.join(souls_dir, "good")
            os.makedirs(good_dir)
            with open(os.path.join(good_dir, "soul.json"), "w", encoding="utf-8") as f:
                f.write('{"name": "good", "displayName": "Good", "archetype": "General"}')
            with open(os.path.join(good_dir, "SOUL.md"), "w", encoding="utf-8") as f:
                f.write("x" * 60)
            bad_dir = os.path.join(souls_dir, "bad")
            os.makedirs(bad_dir)
            with open(os.path.join(bad_dir, "soul.json"), "w", encoding="utf-8") as f:
                f.write("{broken json")
            with open(os.path.join(bad_dir, "SOUL.md"), "w", encoding="utf-8") as f:
                f.write("y" * 60)
            engine = SoulEngine(souls_dir=souls_dir, config_dir=config_dir)
            self.assertIsNotNone(engine.get_soul("good"))
            self.assertIsNone(engine.get_soul("bad"))
            self.assertIn("bad", engine.load_errors)


class TestSoulCLI(unittest.TestCase):
    """Test Click CLI command suite for souls."""

    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_cli_soul_list(self) -> None:
        result = self.runner.invoke(soul_group, ["list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Saleha Cognitive Personas (SoulSpec v1.0)", result.output)
        self.assertIn("sovereign", result.output)
        self.assertIn("architect", result.output)
        self.assertIn("sentinel", result.output)

    def test_cli_soul_use(self) -> None:
        result = self.runner.invoke(soul_group, ["use", "speedrunner"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Soul Transition Complete", result.output)
        self.assertIn("Speedrunner", result.output)

        # Revert back to sovereign
        rev = self.runner.invoke(soul_group, ["use", "sovereign"])
        self.assertEqual(rev.exit_code, 0)

    def test_cli_soul_show(self) -> None:
        result = self.runner.invoke(soul_group, ["show", "auditor"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Formal Verification Auditor", result.output)
        self.assertIn("Lean 4", result.output)

    def test_cli_soul_validate(self) -> None:
        result = self.runner.invoke(soul_group, ["validate"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("All 10 SoulSpec personas are 100% valid and verified", result.output)


if __name__ == "__main__":
    unittest.main()
