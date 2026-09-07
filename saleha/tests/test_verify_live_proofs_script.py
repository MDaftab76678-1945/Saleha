"""
Guard tests for `scripts/verify_all_live_proofs.py`.

That script sat broken for an unknown length of time: an earlier pass rewrote
`formal_smt_verifier` to stop fabricating proofs, changing its result fields,
and the script still read `proof.preconditions` / `proof.is_satisfiable`. It
died with an AttributeError partway through -- and nobody noticed, because
nothing imports it and nothing runs it.

These tests make the script's own contract enforceable: it must import, its
checks must return real booleans, and it must not reintroduce the constant
"100% success" banner it used to print before looking at any result.
"""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import unittest
from unittest.mock import patch

SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "verify_all_live_proofs.py",
)


def load_script():
    spec = importlib.util.spec_from_file_location("verify_all_live_proofs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScriptContractTests(unittest.TestCase):
    """The script must stay in step with the modules it calls."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_script()

    def test_script_imports_without_error(self):
        """It previously crashed on fields that no longer existed."""
        self.assertTrue(hasattr(self.mod, "main"))

    def test_smt_check_uses_fields_the_verifier_actually_has(self):
        from saleha.core.formal_smt_verifier import FormalProofContract
        fields = set(FormalProofContract.__dataclass_fields__)
        # The fields the script reads must all exist on the real result.
        for name in ("z3_available", "divisions_found", "divisions_proven_safe",
                     "divisions_not_analyzed", "proof_duration_ms",
                     "mathematical_certificate"):
            self.assertIn(name, fields)
        # And the ones it used to read must be gone, so this test fails loudly
        # if the fabricated API ever comes back.
        self.assertNotIn("preconditions", fields)
        self.assertNotIn("is_satisfiable", fields)

    def test_no_hardcoded_success_banner(self):
        """
        Check the executable strings only. The docstrings deliberately quote
        the old fabricated banners to explain what was removed, so a plain
        text search over the file would match its own history note.
        """
        import ast as _ast
        with open(SCRIPT, encoding="utf-8") as fh:
            tree = _ast.parse(fh.read())

        docstrings = set()
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.Module, _ast.FunctionDef,
                                 _ast.AsyncFunctionDef, _ast.ClassDef)):
                doc = _ast.get_docstring(node, clean=False)
                if doc:
                    docstrings.add(doc)

        literals = [
            n.value for n in _ast.walk(tree)
            if isinstance(n, _ast.Constant) and isinstance(n.value, str)
            and n.value not in docstrings
        ]
        joined = "\n".join(literals)
        self.assertNotIn("100% SUCCESS", joined)
        self.assertNotIn("100% Synced", joined)
        self.assertNotIn("PROOFS VERIFIED", joined)

    def test_checks_return_booleans(self):
        from rich.console import Console
        console = Console(file=io.StringIO())
        for name in ("check_datasets", "check_fuzz", "check_indexer", "check_git"):
            result = getattr(self.mod, name)(console)
            self.assertIsInstance(result, bool, name)

    def test_missing_dataset_makes_the_dataset_check_fail(self):
        """The old banner printed 100% success over rows reading MISSING."""
        from rich.console import Console
        console = Console(file=io.StringIO())
        with patch.object(self.mod, "DATASET_FILES", ["datasets/does_not_exist.jsonl"]):
            self.assertFalse(self.mod.check_datasets(console))

    def test_main_returns_nonzero_when_a_check_fails(self):
        from rich.console import Console
        with patch.object(self.mod, "DATASET_FILES", ["datasets/does_not_exist.jsonl"]), \
             patch.object(self.mod, "Console",
                          lambda *a, **k: Console(file=io.StringIO())):
            self.assertEqual(self.mod.main(), 1)

    def test_a_raising_check_counts_as_failed_not_passed(self):
        from rich.console import Console
        with patch.object(self.mod, "check_indexer",
                          side_effect=RuntimeError("boom")), \
             patch.object(self.mod, "Console",
                          lambda *a, **k: Console(file=io.StringIO())):
            self.assertEqual(self.mod.main(), 1)

    def test_git_check_reads_real_state_not_a_literal(self):
        from rich.console import Console
        buf = io.StringIO()
        self.mod.check_git(Console(file=buf, width=200))
        output = buf.getvalue()
        self.assertIn("branch", output)
        # The real upstream comparison, not the old fixed string.
        self.assertNotIn("100% Synced", output)


if __name__ == "__main__":
    unittest.main()
