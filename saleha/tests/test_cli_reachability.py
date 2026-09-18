"""Structural tests: every shipped CLI command must actually be invocable.

These exist because of a defect class the 1900-test suite cannot see. Saleha's
CLI commands import their dependencies *inside* the command body, for lazy
loading. That means a stale import name does not break module import, does not
break collection, and does not fail a single test -- it raises ImportError only
when a human runs the command.

Four commands shipped broken that way in one morning (2026-09-18, pass 56):
`swe_bench_harness.swe_bench` and `swe_leaderboard.swe_leaderboard` were renamed
in saleha/core/, and the call sites in testing_bench.py and misc_tools.py kept
the dead names. The suite stayed green at 1912 passed throughout.

A `--help` smoke test does not help: Click renders help from the decorators
without entering the function body, so all 158 commands answer `--help` in
0.1s while the bodies are broken. That was measured before writing this file.

What does work is checking the structure without executing it:

* resolve every function-local `from saleha... import X` and confirm X exists;
* confirm no command name is registered twice.

Replayed against the broken commit, the first check catches all four
regressions by file and line. The second catches the shadowing bug that made
`saleha benchmark` resolve to one command and leave another unreachable -- the
same shape as the duplicate `solve-issue` found in pass 30.
"""

import ast
import collections
import importlib
import re
import unittest
from pathlib import Path
from typing import List, Tuple


CLI_DIR = Path(__file__).resolve().parents[1] / "cli"

# Both decorator spellings register onto the same Click group. An earlier scan
# only looked for @cli.command and therefore missed the benchmark collision,
# which is declared with @click.command in one of the two files.
_COMMAND_DECORATOR = re.compile(
    r"@(?:cli|click)\.command\(\s*(?:name\s*=\s*)?['\"]([\w-]+)['\"]"
)


def _iter_cli_sources() -> List[Path]:
    return sorted(CLI_DIR.rglob("*.py"))


def _function_local_saleha_imports(path: Path) -> List[Tuple[int, str, str]]:
    """Every `from saleha... import NAME` that sits inside a function body.

    Module-level imports are deliberately excluded: those already fail loudly
    at import time, so the test suite catches them. It is the lazy ones inside
    command bodies that stay invisible.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"),
                         filename=str(path))
    except SyntaxError:  # a syntax error is a different test's job
        return []

    found: List[Tuple[int, str, str]] = []
    for func in (n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        for node in ast.walk(func):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not node.module or not node.module.startswith("saleha"):
                continue
            for alias in node.names:
                found.append((node.lineno, node.module, alias.name))
    return found


class LazyImportsResolveTests(unittest.TestCase):
    """A command body's imports must name things that exist."""

    def test_every_function_local_saleha_import_resolves(self) -> None:
        broken: List[str] = []
        checked = 0

        for path in _iter_cli_sources():
            for lineno, module, name in _function_local_saleha_imports(path):
                checked += 1
                try:
                    mod = importlib.import_module(module)
                except Exception as exc:  # noqa: BLE001 - report, don't mask
                    broken.append(
                        f"{path.name}:{lineno} `from {module} import {name}` "
                        f"-> {type(exc).__name__}: {exc}"
                    )
                    continue
                if not hasattr(mod, name):
                    broken.append(
                        f"{path.name}:{lineno} `from {module} import {name}` "
                        f"-> {module} has no attribute '{name}'"
                    )

        self.assertGreater(checked, 50,
                           "scan found almost no lazy imports -- it has "
                           "probably stopped matching the real code shape")
        self.assertEqual(
            broken, [],
            "These CLI commands raise ImportError the moment a user runs "
            "them. The module still imports and the suite still passes, "
            "which is exactly why this check exists:\n  "
            + "\n  ".join(broken),
        )


class CommandNameCollisionTests(unittest.TestCase):
    """Two commands sharing a name means one of them is unreachable."""

    def test_no_command_name_is_declared_twice(self) -> None:
        declared = collections.defaultdict(list)

        for path in _iter_cli_sources():
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in _COMMAND_DECORATOR.finditer(text):
                line = text[:match.start()].count("\n") + 1
                declared[match.group(1)].append(f"{path.name}:{line}")

        collisions = {name: where for name, where in declared.items()
                      if len(where) > 1}

        self.assertEqual(
            collisions, {},
            "A command name registered in two places silently loses one of "
            "them -- Click keeps whichever is registered last, and the other "
            "cannot be invoked at all (pass 30 found this with a duplicated "
            "`solve-issue`):\n  "
            + "\n  ".join(f"{n}: {w}" for n, w in collisions.items()),
        )


if __name__ == "__main__":
    unittest.main()
