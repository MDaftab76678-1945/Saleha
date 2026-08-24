"""v1.1 Agentic Loop tests -- scripted fake agents (deterministic)."""
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from saleha.core.agentic_loop import AgentLoop, LoopResult


class ScriptedAgent:
    """Har think() call pe agla scripted response deta hai."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def think(self, prompt, **kwargs):
        self.prompts.append(prompt)
        resp = MagicMock()
        if isinstance(self.responses[0], Exception):
            raise self.responses.pop(0)
        content = self.responses.pop(0)
        resp.success = True
        resp.content = content
        return resp


def _tool_call(name, **args):
    return f'```tool_call\n{{"tool": "{name}", "args": {json.dumps(args)}}}\n```'


def _finish(summary="done"):
    return f'```json\n{{"finish": "{summary}"}}\n```'


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        with open(os.path.join(self.root, "app.py"), "w") as f:
            f.write("def charge(amount):\n    return amount * 2\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_read_then_finish_success(self):
        agent = ScriptedAgent([
            _tool_call("read_file", path="app.py"),
            _finish("found charge function"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root)
        res = loop.run("understand billing")
        self.assertTrue(res.success, res.error)
        self.assertEqual(res.final_message, "found charge function")
        self.assertEqual(res.steps[0].action, "read_file")
        self.assertIn("def charge", res.steps[0].observation)

    def test_run_code_observation(self):
        agent = ScriptedAgent([
            _tool_call("run_code", code="print(6*7)"),
            _finish("computed"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("compute answer")
        self.assertTrue(res.success)
        self.assertIn("42", res.steps[0].observation)
        self.assertIn("exit=0", res.steps[0].observation)

    def test_search_repo_finds_match(self):
        agent = ScriptedAgent([
            _tool_call("search_repo", pattern="charge"),
            _finish("located"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("find charge")
        obs = res.steps[0].observation
        self.assertIn("app.py:1", obs)

    def test_max_steps_exhaustion_fails(self):
        agent = ScriptedAgent([_tool_call("list_dir", path=".")] * 5)
        res = AgentLoop(agent=agent, root_dir=self.root, max_steps=3).run("loop forever")
        self.assertFalse(res.success)
        self.assertIn("max_steps", res.error)
        self.assertEqual(len(res.steps), 3)

    def test_path_traversal_blocked(self):
        agent = ScriptedAgent([
            _tool_call("read_file", path="../../etc/passwd"),
            _finish("tried"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("escape")
        self.assertIn("no such file", res.steps[0].observation)

    def test_unknown_tool_reported(self):
        agent = ScriptedAgent([
            _tool_call("delete_everything"),
            _finish("ok"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("chaos")
        self.assertIn("unknown tool", res.steps[0].observation)

    def test_write_disabled_by_default(self):
        agent = ScriptedAgent([
            _tool_call("write_file", path="new.py", content="x=1"),
            _finish("attempted write"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("write something")
        self.assertFalse(os.path.exists(os.path.join(self.root, "new.py")))
        self.assertIn("BLOCKED", res.steps[0].observation)

    def test_write_with_allow_and_approval_writes(self):
        agent = ScriptedAgent([
            _tool_call("write_file", path="notes/new.py", content="x=1"),
            _finish("written"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root, allow_write=True)
        with patch_gate(approve_result=True):
            res = loop.run("write notes")
        self.assertTrue(res.success)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "notes", "new.py")))

    def test_on_event_streaming(self):
        events = []
        agent = ScriptedAgent([
            _tool_call("list_dir", path="."),
            _finish("listed"),
        ])
        AgentLoop(agent=agent, root_dir=self.root).run(
            "explore", on_event=events.append)
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[-1]["action"], "finish")


class patch_gate:
    """approval_gate.approve ko force-approve karta hai (context manager)."""
    def __init__(self, approve_result=True):
        self.result = approve_result
        self._cm = None

    def __enter__(self):
        from unittest.mock import patch
        import saleha.core.approval_gate as gate
        self._cm = patch.object(gate, "approve",
                                lambda *a, **k: self.result)
        self._cm.__enter__()
        # agentic_loop function-local import karta hai -- module attr patched hai
        import saleha.core.approval_gate as gate2
        assert gate2.approve  # sanity
        return self

    def __exit__(self, *a):
        return self._cm.__exit__(*a)


if __name__ == "__main__":
    unittest.main()
