"""saleha fix: a fix is kept only when its receipt proves it; otherwise the repo is left as it was."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, List

from saleha.core.loop import fix_flow
from saleha.tests.agents.test_agentic_loop import ScriptedAgent, _finish, _tool_call

BUGGY = "def add(a, b):\n    return a - b\n"
TEST = "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]


def _git(root: str, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    return p.stdout


class _NoModel:
    def think(self, *_a: Any, **_k: Any) -> Any:
        raise AssertionError("the agent must not be called")


class FixFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name
        Path(self.root, "calc.py").write_bytes(BUGGY.encode())
        Path(self.root, "test_calc.py").write_bytes(TEST.encode())
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "t")
        _git(self.root, "config", "core.autocrlf", "false")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "init")
        self.state = os.path.join(self.root, "..", os.path.basename(self.root) + "-state")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _fix(self, responses: List[Any]) -> fix_flow.FixResult:
        return fix_flow.fix_repo(
            self.root, model="scripted", test_command=PYTEST, max_steps=8, timeout=120,
            agent_factory=lambda _m: ScriptedAgent(responses) if responses else _NoModel(),
            ledger_path=os.path.join(self.state, "ledger.jsonl"),
            anchor_path=os.path.join(self.state, "anchors.jsonl"))

    def test_a_proven_fix_is_kept(self) -> None:
        res = self._fix([
            _tool_call("read_file", path="test_calc.py"),
            _tool_call("read_file", path="calc.py"),
            _tool_call("patch_file", path="calc.py", search="a - b", replace="a + b"),
            _finish("fixed"), _finish("fixed"), _finish("fixed"),
        ])
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        assert res.receipt is not None
        self.assertEqual(res.receipt["verdict"], "PROVEN")
        self.assertEqual(res.changed_files, ["calc.py"])
        self.assertEqual(res.failing_before, ["test_calc.py::test_add"])
        self.assertIn("a + b", Path(self.root, "calc.py").read_text(encoding="utf-8"))

    def test_an_unproven_fix_is_taken_back_out(self) -> None:
        res = self._fix([
            _tool_call("read_file", path="test_calc.py"),
            _tool_call("read_file", path="calc.py"),
            _tool_call("patch_file", path="calc.py", search="a - b", replace="a * b"),
        ] + [_finish("fixed")] * 6)
        self.assertEqual(res.verdict, fix_flow.NOT_FIXED, res.reason)
        self.assertIn("reverted", res.reason)
        self.assertEqual(Path(self.root, "calc.py").read_bytes(), BUGGY.encode())
        self.assertEqual(_git(self.root, "status", "--porcelain").strip(), "")

    def test_uncommitted_work_is_never_touched(self) -> None:
        Path(self.root, "calc.py").write_bytes(b"def add(a, b):\n    return b - a\n")
        res = self._fix([])
        self.assertEqual(res.verdict, fix_flow.CANNOT_RUN)
        self.assertIn("uncommitted", res.reason)
        self.assertEqual(Path(self.root, "calc.py").read_bytes(), b"def add(a, b):\n    return b - a\n")

    def test_a_passing_suite_calls_no_model(self) -> None:
        Path(self.root, "calc.py").write_bytes(b"def add(a, b):\n    return a + b\n")
        _git(self.root, "commit", "-q", "-am", "good")
        res = self._fix([])
        self.assertEqual(res.verdict, fix_flow.ALREADY_PASSING, res.reason)
        self.assertTrue(res.ok)

    def test_leftover_bytecode_is_neither_dirt_nor_part_of_the_fix(self) -> None:
        # Not calc's own cache: patch_file drops the patched module's stale bytecode.
        cache = Path(self.root, "__pycache__")
        cache.mkdir()
        (cache / "other.cpython-312.pyc").write_bytes(b"junk")
        res = self._fix([
            _tool_call("read_file", path="test_calc.py"),
            _tool_call("read_file", path="calc.py"),
            _tool_call("patch_file", path="calc.py", search="a - b", replace="a + b"),
            _finish("fixed"), _finish("fixed"), _finish("fixed"),
        ])
        self.assertEqual(res.verdict, fix_flow.FIXED, res.reason)
        self.assertEqual(res.changed_files, ["calc.py"])
        assert res.receipt is not None
        self.assertEqual(res.receipt["changed_files"], ["calc.py"])
        self.assertTrue((cache / "other.cpython-312.pyc").exists(), "caches found there stay")
        self.assertEqual(_git(self.root, "status", "--porcelain", "--untracked-files=all").split(),
                         ["M", "calc.py", "??", "__pycache__/other.cpython-312.pyc"])

    def test_not_a_git_repo_cannot_be_proven(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as bare:
            res = fix_flow.fix_repo(bare, test_command=PYTEST, agent_factory=lambda _m: _NoModel())
        self.assertEqual(res.verdict, fix_flow.CANNOT_RUN)
        self.assertIn("not a git repository", res.reason)


class FixCommandTests(unittest.TestCase):
    def test_the_cli_reports_a_repo_it_cannot_prove_in_json_and_exits_1(self) -> None:
        import json

        from click.testing import CliRunner

        from saleha.cli.commands import cli
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as bare:
            res = CliRunner().invoke(cli, ["fix", "--dir", bare, "--json"])
        self.assertEqual(res.exit_code, 1, res.output)
        out = json.loads(res.output.strip().splitlines()[-1])
        self.assertEqual(out["verdict"], "CANNOT_RUN")
        self.assertFalse(out["ok"])


def _ci_report_module() -> Any:
    import importlib.util
    path = Path(__file__).resolve().parents[3] / "scripts" / "ci_fix_report.py"
    spec = importlib.util.spec_from_file_location("ci_fix_report", str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CiFixReportTests(unittest.TestCase):
    """The GitHub Action's reading of `saleha fix --json`."""

    def test_unreadable_output_is_a_harness_error_not_a_pass(self) -> None:
        mod = _ci_report_module()
        res = mod.read_result(os.path.join(tempfile.gettempdir(), "no-such-saleha-fix.json"))
        self.assertEqual(res["verdict"], "HARNESS_ERROR")
        self.assertFalse(res["ok"])

    def test_outputs_and_summary_for_a_proven_fix(self) -> None:
        from unittest.mock import patch
        mod = _ci_report_module()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            src = Path(d, "fix.json")
            src.write_text("progress noise\n" + '{"verdict": "FIXED", "ok": true, "branch": "saleha/fix-1", '
                           '"reason": "proven", "receipt_markdown": "# Proof receipt: PROVEN\\n"}\n',
                           encoding="utf-8")
            out, summ = Path(d, "out"), Path(d, "summary")
            with patch.dict(os.environ, {"GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summ)}), \
                 patch("sys.argv", ["ci_fix_report.py", str(src), str(Path(d, "body.md"))]):
                mod.main()
            self.assertEqual(out.read_text(encoding="utf-8").split(),
                             ["verdict=FIXED", "branch=saleha/fix-1", "ok=true"])
            self.assertIn("Proof receipt: PROVEN", summ.read_text(encoding="utf-8"))
            self.assertIn("proved the fix", Path(d, "body.md").read_text(encoding="utf-8"))


class FixFlowHelperTests(unittest.TestCase):
    def test_failing_tests_are_read_from_the_short_summary(self) -> None:
        out = ("..F\nFAILED tests/test_x.py::test_a - assert 1 == 2\n"
               "ERROR tests/test_y.py::test_b\n1 failed, 1 error")
        self.assertEqual(fix_flow.failing_tests(out),
                         [("tests/test_x.py::test_a", "assert 1 == 2"), ("tests/test_y.py::test_b", "")])

    def test_a_windows_command_with_a_quoted_path_splits_cleanly(self) -> None:
        cmd = '"C:\\Program Files\\Py\\python.exe" -m pytest -q tests'
        if os.name == "nt":
            self.assertEqual(fix_flow.split_command(cmd),
                             ["C:\\Program Files\\Py\\python.exe", "-m", "pytest", "-q", "tests"])
        self.assertEqual(fix_flow.split_command("python -m pytest -q"), ["python", "-m", "pytest", "-q"])

    def test_saleha_test_python_picks_the_interpreter_for_the_projects_tests(self) -> None:
        from unittest.mock import patch

        from saleha.core.loop.agentic_loop import discover_test_command
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            Path(d, "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
            with patch.dict(os.environ, {"SALEHA_TEST_PYTHON": "/job/python3"}):
                argv, _why = discover_test_command(d)
            plain, _ = discover_test_command(d)
        self.assertEqual(argv, ["/job/python3", "-m", "pytest", "-q"])
        assert plain is not None
        self.assertEqual(plain[0], sys.executable)

    def test_generated_paths(self) -> None:
        for p in ("__pycache__/a.pyc", "pkg/__pycache__/b.cpython-312.pyc", ".saleha/work.jsonl",
                  ".pytest_cache/v/x", "mod.pyc"):
            self.assertTrue(fix_flow.is_generated(p), p)
        for p in ("calc.py", "tests/test_calc.py", "saleha_notes.md"):
            self.assertFalse(fix_flow.is_generated(p), p)


if __name__ == "__main__":
    unittest.main()
