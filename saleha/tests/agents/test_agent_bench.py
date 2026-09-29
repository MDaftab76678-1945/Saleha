import json
import unittest
from typing import Any, List, Optional

from saleha.agents.base_agent import AgentResponse
from saleha.core.harness.agent_bench import AGENT_TASKS, AgentTask, check_task, run_task


class TaskGateTests(unittest.TestCase):
    """Every task must be able to tell a fixed repo from a buggy one."""

    def test_every_task_fails_buggy_and_passes_fixed(self) -> None:
        for task in AGENT_TASKS:
            with self.subTest(task=task.task_id):
                self.assertEqual(check_task(task), "")

    def test_a_hidden_test_that_cannot_fail_is_refused(self) -> None:
        weak = AgentTask("weak", "g", {"m.py": "X = 1\n"}, {"m.py": "X = 2\n"}, "def test_x():\n    assert True\n")
        self.assertIn("pass on the buggy repo", check_task(weak))

    def test_a_wrong_reference_fix_is_refused(self) -> None:
        bad = AgentTask("bad", "g", {"m.py": "X = 1\n"}, {"m.py": "X = 3\n"},
                        "import m\ndef test_x():\n    assert m.X == 2\n")
        self.assertIn("fail on the reference fix", check_task(bad))

    def test_ids_are_unique(self) -> None:
        ids = [t.task_id for t in AGENT_TASKS]
        self.assertEqual(len(ids), len(set(ids)))


class StaleBytecodeGradingTests(unittest.TestCase):
    def test_the_grade_ignores_a_stale_pyc_left_in_the_repo(self) -> None:
        """Same size, same second: the repo's .pyc still holds the old code."""
        import os
        import subprocess
        import sys
        import tempfile

        from saleha.core.harness.agent_bench import run_hidden_test

        hidden = "from calc import f\n\ndef test_f():\n    assert f() == 0\n"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
            path = os.path.join(root, "calc.py")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("def f():\n    return 1 + 1\n")
            subprocess.run([sys.executable, "-c", "import calc"], cwd=root, check=True)  # writes the .pyc
            old = os.stat(path).st_mtime
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("def f():\n    return 1 - 1\n")
            os.utime(path, (old, old))
            ok, detail = run_hidden_test(root, hidden)
        self.assertTrue(ok, detail)


class _Scripted:
    def __init__(self, replies: List[str]) -> None:
        self.replies = replies

    def think(self, prompt: str, previous_error_reflexion: Optional[str] = None,
              complexity_score: float = 0.0, disable_reasoning: bool = False, **kw: Any) -> AgentResponse:
        return AgentResponse(success=True, content=self.replies.pop(0) if self.replies else "")


def _call(tool: str, **args: Any) -> str:
    return f'```tool_call\n{{"tool": "{tool}", "args": {json.dumps(args)}}}\n```'


class GradingTests(unittest.TestCase):
    """Solved is decided by the hidden tests, never by the agent's claim."""

    TASK = next(t for t in AGENT_TASKS if t.task_id == "pager_off_by_one")

    def test_a_real_fix_is_solved(self) -> None:
        agent = _Scripted([_call("patch_file", path="shop/pager.py",
                                 search="start + size + 1]", replace="start + size]"),
                           '```json\n{"finish": "fixed"}\n```'])
        out = run_task(self.TASK, lambda: agent, max_steps=4)
        self.assertTrue(out.solved, out.detail)

    def test_a_claimed_fix_that_changed_nothing_is_not_solved(self) -> None:
        agent = _Scripted([_call("list_dir", path="."), '```json\n{"finish": "fixed it"}\n```'])
        out = run_task(self.TASK, lambda: agent, max_steps=4)
        self.assertFalse(out.solved)

    def test_the_agent_never_sees_the_hidden_tests(self) -> None:
        seen: List[str] = []

        class Peek(_Scripted):
            def think(self, prompt: str, *a: Any, **k: Any) -> AgentResponse:
                seen.append(prompt)
                return super().think(prompt, *a, **k)

        run_task(self.TASK, lambda: Peek([_call("list_dir", path=".")]), max_steps=2)
        self.assertTrue(seen)
        self.assertFalse(any("page(data, 4, 3)" in p for p in seen))


if __name__ == "__main__":
    unittest.main()
