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

    def test_patch_file_tool(self):
        agent = ScriptedAgent([
            _tool_call("patch_file", path="app.py", search="amount * 2", replace="amount * 10"),
            _finish("patched"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root, allow_write=True)
        with patch_gate(approve_result=True):
            res = loop.run("patch charge")
        self.assertTrue(res.success)
        with open(os.path.join(self.root, "app.py"), "r") as f:
            self.assertIn("amount * 10", f.read())

    def test_get_file_outline_and_find_symbols(self):
        agent = ScriptedAgent([
            _tool_call("get_file_outline", path="app.py"),
            _tool_call("find_symbols", symbol_name="charge"),
            _finish("inspected"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root)
        res = loop.run("inspect code")
        self.assertTrue(res.success)
        self.assertIn("def charge()", res.steps[0].observation)
        self.assertIn("app.py", res.steps[1].observation)

    def test_deepseek_r1_think_parsing(self):
        events = []
        agent = ScriptedAgent([
            "<think>Analyzing billing function to verify rate logic.</think>\n"
            + _tool_call("read_file", path="app.py"),
            "<think>I found the charge function and it looks correct.</think>\n"
            + _finish("verified charge function"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root)
        res = loop.run("check charge", on_event=events.append)
        self.assertTrue(res.success)
        self.assertEqual(res.final_message, "verified charge function")
        # Ensure think events were emitted
        think_events = [e for e in events if e.get("action") == "think"]
        self.assertGreaterEqual(len(think_events), 2)
        self.assertIn("Analyzing billing", think_events[0]["thought"])

    def test_premature_finish_rejected_then_recovers(self):
        """Real bug found running Saleha against actual SWE-bench instances:
        a small model called finish() on turn 1 with zero prior tool calls,
        hallucinating completion. finish() must be rejected until at least
        one real tool call happened, and the loop must give the model a
        chance to recover afterward rather than failing outright."""
        agent = ScriptedAgent([
            _finish("File read successfully"),  # premature -- nothing read yet
            _tool_call("read_file", path="app.py"),
            _finish("found charge function"),
        ])
        events = []
        res = AgentLoop(agent=agent, root_dir=self.root).run(
            "understand billing", on_event=events.append)
        self.assertTrue(res.success, res.error)
        self.assertEqual(res.final_message, "found charge function")
        # The premature finish must not count as a real step.
        self.assertEqual(len(res.steps), 2)  # read_file + the accepted finish
        self.assertEqual(res.steps[0].action, "read_file")
        rejected = [e for e in events if e.get("action") == "finish-rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertIn("REJECTED", rejected[0]["observation"])

    def test_repeated_premature_finish_exhausts_max_steps(self):
        """If the model never takes a real action, it must not be able to
        force a false success by just repeating finish()."""
        agent = ScriptedAgent([_finish("done")] * 5)
        res = AgentLoop(agent=agent, root_dir=self.root, max_steps=3).run("do nothing")
        self.assertFalse(res.success)
        self.assertIn("max_steps", res.error)

    def test_min_actions_before_finish_zero_keeps_old_behavior(self):
        """min_actions_before_finish=0 restores immediate-finish (opt-out)."""
        agent = ScriptedAgent([_finish("instant")])
        res = AgentLoop(agent=agent, root_dir=self.root,
                         min_actions_before_finish=0).run("trivial goal")
        self.assertTrue(res.success)
        self.assertEqual(res.final_message, "instant")

    # ------------------------------------------------------------------
    # Evidence-based completion (Level-6 architecture target)
    # ------------------------------------------------------------------

    def test_evidence_gate_rejects_finish_with_no_real_work(self):
        """require_evidence=True: finish() must be refused until the tools
        actually observed the required fact, then accepted once they have."""
        from saleha.core.task_evidence import EvidenceKind, TaskState
        agent = ScriptedAgent([
            _finish("I already fixed it"),          # pure claim, no work
            _tool_call("read_file", path="app.py"),  # real observation
            _finish("found charge function"),
        ])
        events = []
        loop = AgentLoop(agent=agent, root_dir=self.root,
                         require_evidence=True,
                         required_evidence={EvidenceKind.FILE_READ})
        res = loop.run("understand billing", on_event=events.append)

        self.assertTrue(res.success, res.error)
        rejected = [e for e in events if e.get("action") == "finish-rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertIn("no evidence of: file_read", rejected[0]["observation"])
        self.assertEqual(loop.ledger.state, TaskState.ACCEPTED)
        self.assertTrue(loop.ledger.has(EvidenceKind.FILE_READ))

    def test_evidence_gate_never_accepts_without_the_required_kind(self):
        """A model that only ever searches cannot satisfy a FILE_READ
        requirement, so the run honestly exhausts max_steps."""
        from saleha.core.task_evidence import EvidenceKind, TaskState
        agent = ScriptedAgent([
            _tool_call("list_dir", path="."),
            _finish("done"),
            _tool_call("list_dir", path="."),
            _finish("done"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root, max_steps=4,
                         require_evidence=True,
                         required_evidence={EvidenceKind.FILE_READ})
        res = loop.run("look around")
        self.assertFalse(res.success)
        self.assertIn("max_steps", res.error)
        self.assertEqual(loop.ledger.state, TaskState.FAILED)

    def test_failed_tool_call_produces_no_evidence(self):
        """A tool that errored proves nothing and must not count as work."""
        from saleha.core.task_evidence import EvidenceKind
        agent = ScriptedAgent([
            _tool_call("read_file", bad_arg="x"),   # wrong kwarg -> TypeError
            _finish("done anyway"),
            _tool_call("read_file", path="app.py"),
            _finish("really done"),
        ])
        events = []
        loop = AgentLoop(agent=agent, root_dir=self.root, max_steps=6,
                         require_evidence=True,
                         required_evidence={EvidenceKind.FILE_READ})
        res = loop.run("read the file", on_event=events.append)
        self.assertTrue(res.success, res.error)
        # The first finish was rejected because the failed call gave no evidence.
        rejected = [e for e in events if e.get("action") == "finish-rejected"]
        self.assertEqual(len(rejected), 1)
        # Exactly one FILE_READ evidence -- from the successful call only.
        reads = [e for e in loop.ledger.evidence if e.kind == EvidenceKind.FILE_READ]
        self.assertEqual(len(reads), 1)

    def test_write_evidence_moves_state_to_implementing(self):
        from saleha.core.task_evidence import EvidenceKind, TaskState
        agent = ScriptedAgent([
            _tool_call("write_file", path="new.py", content="x = 1\n"),
            _finish("wrote it"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                         require_evidence=True,
                         required_evidence={EvidenceKind.FILE_MODIFIED})
        res = loop.run("create a file")
        self.assertTrue(res.success, res.error)
        self.assertTrue(loop.ledger.has(EvidenceKind.FILE_MODIFIED))
        states = [h["state"] for h in loop.ledger.history]
        self.assertIn("IMPLEMENTING", states)
        self.assertEqual(loop.ledger.state, TaskState.ACCEPTED)

    def test_budget_stops_a_runaway_loop(self):
        """max_tool_calls must actually halt the run, not just be advisory."""
        from saleha.core.task_evidence import EvidenceKind, ResourceBudget, TaskState
        agent = ScriptedAgent([_tool_call("list_dir", path=".")] * 10)
        loop = AgentLoop(agent=agent, root_dir=self.root, max_steps=10,
                         require_evidence=True,
                         required_evidence={EvidenceKind.FILE_READ},
                         budget=ResourceBudget(max_tool_calls=3))
        res = loop.run("loop forever")
        self.assertFalse(res.success)
        self.assertIn("budget exceeded", res.error)
        self.assertEqual(loop.ledger.state, TaskState.FAILED)
        self.assertEqual(len(res.steps), 4)  # 3 allowed, 4th trips the limit

    def test_evidence_off_by_default_keeps_old_behaviour(self):
        """Existing callers must be unaffected: no ledger, no gate."""
        agent = ScriptedAgent([
            _tool_call("read_file", path="app.py"),
            _finish("done"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root)
        res = loop.run("understand billing")
        self.assertTrue(res.success, res.error)
        self.assertIsNone(loop.ledger)

    def test_structured_xml_tool_call_and_thinking_parsing(self):
        events = []
        agent = ScriptedAgent([
            "<THINKING>Formulating plan to read and analyze app.py code structure.</THINKING>\n"
            + '<tool_call>{"name": "read_file", "arguments": {"path": "app.py"}}</tool_call>',
            "<THINKING>Verification complete, returning summary.</THINKING>\n"
            + _finish("structured loop completed"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root)
        res = loop.run("inspect via structured loop", on_event=events.append)
        self.assertTrue(res.success, res.error)
        self.assertEqual(res.final_message, "structured loop completed")
        self.assertEqual(res.steps[0].action, "read_file")
        self.assertIn("def charge", res.steps[0].observation)
        think_events = [e for e in events if e.get("action") == "think"]
        self.assertGreaterEqual(len(think_events), 2)
        self.assertIn("Formulating plan", think_events[0]["thought"])


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
