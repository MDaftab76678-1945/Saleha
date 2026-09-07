"""
Guard tests for `saleha/sandbox/`.

`NOTEBOOK_IMPORT.md` imported this directory and called it the "**Real
sandbox** -- `saleha/core/` only has sandbox theater". On the machine that
note was written on, two of its four modules could not be imported at all:

    saleha.sandbox.sandbox_jail       -> ModuleNotFoundError: 'resource'
    saleha.sandbox.v5_production_core -> ModuleNotFoundError: 'local_llm_driver'

The first is a genuine platform limit (`resource` is POSIX-only) that was
unguarded, so it surfaced as a confusing stdlib error. The second was a plain
packaging bug: flat imports for files inside a package, which only resolve
when that directory is the working directory.

These tests keep both fixed, and pin the property that matters more than
either: the jail must refuse where it cannot enforce its limits, rather than
running code unconfined and reporting it as sandboxed.
"""

from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch


class ImportTests(unittest.TestCase):
    """Every module in the package must import on every platform."""

    MODULES = (
        "saleha.sandbox",
        "saleha.sandbox.sandbox_jail",
        "saleha.sandbox.ast_security_verifier",
        "saleha.sandbox.local_llm_driver",
        "saleha.sandbox.v5_production_core",
    )

    def test_every_module_imports(self):
        for name in self.MODULES:
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_no_flat_intra_package_imports(self):
        """
        `from local_llm_driver import ...` resolves only with this directory
        on sys.path. Inside a package it must be the dotted path.
        """
        import ast
        import saleha.sandbox as pkg
        from pathlib import Path

        siblings = {"local_llm_driver", "ast_security_verifier",
                    "sandbox_jail", "v5_production_core"}
        offenders = []
        for path in Path(pkg.__file__).parent.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module in siblings \
                        and node.level == 0:
                    offenders.append(f"{path.name}: from {node.module} import ...")
        self.assertEqual(offenders, [], "; ".join(offenders))


class AvailabilityTests(unittest.TestCase):
    """The jail must be honest about where it can run."""

    def setUp(self):
        from saleha.sandbox.sandbox_jail import HardenedSandbox
        self.HardenedSandbox = HardenedSandbox

    def test_is_available_matches_the_platform(self):
        import os
        import saleha.sandbox.sandbox_jail as mod
        expected = mod.resource is not None and hasattr(os, "fork")
        self.assertEqual(self.HardenedSandbox.is_available(), expected)

    def test_unavailable_reason_is_empty_only_when_available(self):
        reason = self.HardenedSandbox.unavailable_reason()
        if self.HardenedSandbox.is_available():
            self.assertEqual(reason, "")
        else:
            self.assertTrue(reason)
            self.assertIn("resource", reason)

    def test_run_isolated_refuses_rather_than_running_unconfined(self):
        """
        The property this whole file exists for. A sandbox that runs code with
        none of its limits applied, and reports it the same way as a confined
        run, is worse than no sandbox -- the caller believes it is contained.
        """
        from saleha.sandbox.sandbox_jail import SandboxUnavailableError
        import saleha.sandbox.sandbox_jail as mod

        with patch.object(mod, "resource", None):
            with self.assertRaises(SandboxUnavailableError):
                self.HardenedSandbox().run_isolated("print(1)")

    def test_self_healing_engine_refuses_to_construct_without_the_jail(self):
        """
        Every verification path in SelfHealingEngine goes through the jail.
        Failing at construction beats failing partway through a healing run,
        after a model call, with a half-written result.
        """
        from saleha.sandbox.sandbox_jail import SandboxUnavailableError
        from saleha.sandbox.v5_production_core import SelfHealingEngine
        import saleha.sandbox.sandbox_jail as mod

        with patch.object(mod, "resource", None):
            with self.assertRaises(SandboxUnavailableError):
                SelfHealingEngine()


class LedgerAccuracyTests(unittest.TestCase):

    def test_notebook_import_does_not_call_this_unconditionally_real(self):
        """
        The ledger described this directory as the "Real sandbox" with no
        platform qualifier, on a Windows machine where it could not be
        imported. The entry must name the constraint.
        """
        from pathlib import Path
        ledger = Path(__file__).resolve().parents[2] / "NOTEBOOK_IMPORT.md"
        if not ledger.is_file():
            self.skipTest("no NOTEBOOK_IMPORT.md")
        text = ledger.read_text(encoding="utf-8")
        if "sandbox_jail.py" not in text:
            self.skipTest("sandbox_jail not described in the ledger")
        # The line describing it must say POSIX somewhere, so a reader on
        # Windows is not told it is simply "real".
        for line in text.splitlines():
            if "sandbox_jail.py" in line:
                self.assertIn(
                    "POSIX", line,
                    "the ledger entry for sandbox_jail.py must state that it "
                    "is POSIX-only; it cannot be imported on Windows")


if __name__ == "__main__":
    unittest.main()
