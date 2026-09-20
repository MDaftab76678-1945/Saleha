"""v1.1 Agentic Loop tests -- scripted fake agents (deterministic)."""
import json
import os
import tempfile
import unittest
from typing import Any, Optional
from unittest.mock import MagicMock

from saleha.agents.base_agent import AgentResponse
from saleha.core.agentic_loop import (
    MAX_FILE_READ_CHARS,
    MAX_OBSERVATION_CHARS,
    AgentLoop,
    LoopResult,
)


class ScriptedAgent:
    """Returns the next scripted response on each think() call."""

    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.prompts: list = []

    def think(
        self,
        prompt: str,
        previous_error_reflexion: Optional[str] = None,
        complexity_score: float = 0.0,
        disable_reasoning: bool = False,
        **kwargs: Any,
    ) -> AgentResponse:
        self.prompts.append(prompt)
        if isinstance(self.responses[0], Exception):
            raise self.responses.pop(0)
        content = self.responses.pop(0)
        return AgentResponse(success=True, content=content)


def _tool_call(__tool_name: str, **args: Any) -> str:
    return f'```tool_call\n{{"tool": "{__tool_name}", "args": {json.dumps(args)}}}\n```'


def _finish(summary: str = "done") -> str:
    return f'```json\n{{"finish": "{summary}"}}\n```'


class AgentLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        with open(os.path.join(self.root, "app.py"), "w") as f:
            f.write("def charge(amount):\n    return amount * 2\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_read_then_finish_success(self) -> None:
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

    def test_run_code_observation(self) -> None:
        agent = ScriptedAgent([
            _tool_call("run_code", code="print(6*7)"),
            _finish("computed"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("compute answer")
        self.assertTrue(res.success)
        self.assertIn("42", res.steps[0].observation)
        self.assertIn("exit=0", res.steps[0].observation)

    def test_search_repo_finds_match(self) -> None:
        agent = ScriptedAgent([
            _tool_call("search_repo", pattern="charge"),
            _finish("located"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("find charge")
        obs = res.steps[0].observation
        self.assertIn("app.py:1", obs)

    def test_max_steps_exhaustion_fails(self) -> None:
        agent = ScriptedAgent([_tool_call("list_dir", path=".")] * 5)
        res = AgentLoop(agent=agent, root_dir=self.root, max_steps=3).run("loop forever")
        self.assertFalse(res.success)
        self.assertIn("max_steps", res.error)
        self.assertEqual(len(res.steps), 3)

    def test_path_traversal_blocked(self) -> None:
        agent = ScriptedAgent([
            _tool_call("read_file", path="../../etc/passwd"),
            _finish("tried"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("escape")
        self.assertIn("no such file", res.steps[0].observation)

    def test_finish_is_not_offered_before_the_minimum_action_count(self) -> None:
        """Measured against a real repo bug: given a repair goal,
        qwen2.5-coder:3b emits finish() with a prose diagnosis on its very
        first turn, 100% of trials -- even when the prompt explicitly warns
        "finish() is not available until you have called patch_file". A
        text warning did not stop it; removing the finish option from the
        prompt outright did (probed directly: the identical goal, no
        finish() offered at all, got a correct tool call on turn one).
        The first prompt (successful_actions=0 < min_actions_before_finish)
        must not mention finish() as an option. (allow_write left at its
        default False here -- with it on, for a repair goal, a different,
        stricter rule applies; see the mutation-gated test below.)"""
        agent = ScriptedAgent([
            _tool_call("list_dir", path="."),
            _finish("done"),
        ])
        AgentLoop(agent=agent, root_dir=self.root,
                 min_actions_before_finish=1, max_steps=2).run("fix the bug")
        self.assertNotIn('"finish"', agent.prompts[0])
        self.assertIn("no finish() action available", agent.prompts[0])
        # Once the minimum is met, the next prompt must offer it again.
        self.assertIn('"finish"', agent.prompts[1])

    def test_repair_goal_keeps_finish_hidden_until_a_mutation_is_attempted(self) -> None:
        """Measured live (pass 94): one successful list_dir re-armed
        finish() after a single step under the plain successful_actions
        count, and qwen2.5-coder:3b reached for it again immediately
        instead of continuing to patch_file -- min_actions_before_finish=1
        was satisfied by an action that cannot possibly fix anything. For
        a repair goal with allow_write on, "the minimum" must mean an
        attempted edit, not just any successful read."""
        agent = ScriptedAgent([
            _tool_call("list_dir", path="."),
            _finish("done"),
            _finish("done again"),
        ])
        AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                 min_actions_before_finish=1, max_steps=3).run(
            "fix the bug in charge()")
        # list_dir succeeded, but it is not a mutation attempt -- finish()
        # must stay hidden across every prompt that follows it too.
        self.assertNotIn('"finish"', agent.prompts[0])
        self.assertNotIn('"finish"', agent.prompts[1])
        self.assertNotIn('"finish"', agent.prompts[2])

    def test_finish_is_offered_immediately_when_the_minimum_is_zero(self) -> None:
        """A caller that explicitly sets min_actions_before_finish=0 (an
        investigative run with no mandatory tool use) must see finish()
        from the very first prompt -- the gate above must not apply when
        there is nothing to wait for."""
        agent = ScriptedAgent([_finish("done")])
        AgentLoop(agent=agent, root_dir=self.root,
                 min_actions_before_finish=0, max_steps=1).run("look around")
        self.assertIn('"finish"', agent.prompts[0])

    def test_missing_file_names_a_next_action(self) -> None:
        """Measured against a real repo bug: the model guessed
        "utils/super_len.py" (function name, wrong directory) after already
        learning the real path via search_repo two turns earlier -- the old
        bare "no such file" message gave it nothing to connect the two."""
        agent = ScriptedAgent([
            _tool_call("read_file", path="utils/super_len.py"),
            _finish("gave up"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("find the bug")
        self.assertIn("no such file", res.steps[0].observation)
        self.assertIn("DO THIS NEXT", res.steps[0].observation)
        self.assertIn("search_repo", res.steps[0].observation)

    def test_unknown_tool_reported(self) -> None:
        # A third reply is needed because an unknown tool is a FAILED call and
        # no longer satisfies min_actions_before_finish -- the loop rejects the
        # finish and asks again, which is the intended behaviour.
        agent = ScriptedAgent([
            _tool_call("delete_everything"),
            _tool_call("read_file", path="app.py"),
            _finish("ok"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("chaos")
        self.assertIn("unknown tool", res.steps[0].observation)

    def test_failed_call_does_not_license_finish(self) -> None:
        # Measured against a real repo bug: find_symbols crashed with "bad
        # args", the model called finish() next turn, and the run reported
        # success -- because min_actions_before_finish counted appended steps
        # and a crashed call still appends. A call that errored proves nothing.
        agent = ScriptedAgent([
            _tool_call("find_symbols", file_path="app.py"),   # wrong arg name
            _finish("done"),
            _tool_call("read_file", path="app.py"),           # a real action
            _finish("now genuinely done"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("fix it")
        self.assertIn("bad args for find_symbols", res.steps[0].observation)
        # The rejection must name the correct arguments, not just complain.
        rejected = [s for s in res.steps if s.action == "read_file"]
        self.assertTrue(rejected, "the loop never recovered to a real call")
        self.assertTrue(res.success, res.error)
        self.assertEqual(res.final_message, "now genuinely done")

    def test_all_patches_failed_cannot_be_reported_as_done(self) -> None:
        # Measured against a real requests bug: patch_file returned "Could not
        # match search block", the next turn claimed "the patch was applied
        # successfully", and the CLI printed a green tick over an unchanged
        # file. Reads succeeding is not evidence that a write happened.
        agent = ScriptedAgent([
            _tool_call("read_file", path="app.py"),
            _tool_call("patch_file", path="app.py",
                       search="text that is not in the file", replace="x"),
            _finish("the patch was applied successfully"),
            # The loop rejects that finish; the model repeating the claim must
            # not get it accepted either.
            _finish("the patch was applied successfully"),
            _finish("the patch was applied successfully"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                         max_steps=5)
        with patch_gate(approve_result=True):
            res = loop.run("fix the bug")
        self.assertFalse(res.success,
                         "a run whose every patch failed must not report success")
        self.assertIn("patch failed", res.steps[1].observation)

    def test_successful_patch_still_finishes(self) -> None:
        # The guard above must not break the honest path.
        agent = ScriptedAgent([
            _tool_call("patch_file", path="app.py",
                       search="amount * 2", replace="amount * 10"),
            _finish("patched"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root, allow_write=True)
        with patch_gate(approve_result=True):
            res = loop.run("patch charge")
        self.assertTrue(res.success, res.error)
        self.assertEqual(res.final_message, "patched")

    def test_timeout_is_honoured_and_reported(self) -> None:
        # `saleha agent` never passed timeout_sec, so every run silently took
        # the 300s default however large --max-steps was. A qwen3:8b control
        # run against a real repo bug was killed at step 5 by that ceiling
        # while still making genuine progress, so the experiment measured a
        # hardcoded limit rather than the model. This asserts the budget is
        # real and that exhausting it is reported honestly, not as success.
        agent = ScriptedAgent([_tool_call("list_dir", path=".")] * 6)
        loop = AgentLoop(agent=agent, root_dir=self.root, max_steps=6,
                         timeout_sec=0.0)
        res = loop.run("take too long")
        self.assertFalse(res.success)
        self.assertIn("timed out", res.error)

    def test_cli_agent_passes_timeout_through(self) -> None:
        # The parameter existed on AgentLoop and was simply never handed over
        # by the CLI -- a silent gap no test could see. This fails if the
        # argument is dropped again.
        import inspect

        from saleha.cli.commands import core_agentic

        # `agent` is a Click Command, not a function -- inspect needs the
        # underlying callback, which Click types as Optional.
        callback = core_agentic.agent.callback
        self.assertIsNotNone(callback, "saleha agent has no callback")
        assert callback is not None
        src = inspect.getsource(callback)
        self.assertIn("timeout_sec=", src)
        params = inspect.signature(callback).parameters
        self.assertIn("timeout", params)

    def test_unclosed_reasoning_tag_does_not_destroy_the_tool_call(self) -> None:
        # Measured: an unclosed <think> made strip_reasoning delete to
        # end-of-string, taking a perfectly valid tool_call with it, so the
        # loop saw an empty reply and burned a parse-retry. A reasoning model
        # that omits the closer is a normal occurrence, not an error.
        from saleha.core.structured_reasoner import StructuredReasoner

        call = ('```tool_call\n{"tool": "read_file", "args": '
                '{"path": "x.py", "start_line": 160, "end_line": 228}}\n```')
        for opener in ("<think>", "<THINKING>", "<scratchpad>"):
            raw = f"{opener}reasoning that never closes\n{call}"
            clean = StructuredReasoner.strip_reasoning(raw)
            parsed = AgentLoop._parse_call(clean)
            self.assertIsNotNone(
                parsed, f"{opener} destroyed the tool_call: clean={clean!r}")
            self.assertEqual(parsed[0], "read_file")
            self.assertEqual(parsed[1]["start_line"], 160)
            # The reasoning trace itself must still be gone -- leaving it in
            # is what produced a SyntaxError in an earlier pass.
            self.assertNotIn("never closes", clean)

    def test_closed_reasoning_tag_still_strips_and_keeps_the_call(self) -> None:
        from saleha.core.structured_reasoner import StructuredReasoner

        raw = ('<think>short thought</think>\n'
               '```tool_call\n{"tool": "list_dir", "args": {"path": "."}}\n```')
        clean = StructuredReasoner.strip_reasoning(raw)
        self.assertNotIn("short thought", clean)
        self.assertEqual(AgentLoop._parse_call(clean),
                         ("list_dir", {"path": "."}))

    def test_patch_call_with_literal_newlines_in_search_parses(self) -> None:
        # Measured against a real repo bug: a patch_file call whose `search`
        # value spanned several source lines was rejected outright, because
        # json.loads forbids a literal newline inside a string -- and writing
        # the lines verbatim is the natural thing for a model to do when it is
        # copying them out of the file it just read. One wasted step.
        raw = ('```tool_call\n'
               '{"tool": "patch_file", "args": {"path": "utils.py", "search": "'
               'if total_length is None:\n'
               '        total_length = 0\n'
               '", "replace": "pass"}}\n'
               '```')
        parsed = AgentLoop._parse_call(raw)
        self.assertIsNotNone(parsed, "literal newlines in search still reject")
        assert parsed is not None
        self.assertEqual(parsed[0], "patch_file")
        self.assertIn("total_length = 0", parsed[1]["search"])
        self.assertIn("\n", parsed[1]["search"])

    def test_well_formed_payload_is_not_reinterpreted(self) -> None:
        # Strict parsing runs first, so an already-escaped payload must come
        # through byte-identical rather than through the lenient path.
        raw = ('```tool_call\n'
               '{"tool": "patch_file", "args": {"path": "u.py", '
               '"search": "a\\nb", "replace": "c"}}\n'
               '```')
        parsed = AgentLoop._parse_call(raw)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed[1]["search"], "a\nb")

    def test_parser_accepts_the_shapes_models_actually_emit(self) -> None:
        # All of these were probed against the real parser; they are pinned so
        # a future regex change cannot silently start rejecting one.
        shapes = {
            "single line no newline":
                '```tool_call {"tool": "read_file", "args": {"path": "x.py"}} ```',
            "canonical":
                '```tool_call\n{"tool": "read_file", "args": {"path": "x.py"}}\n```',
            "bare json":
                '{"tool": "read_file", "args": {"path": "x.py"}}',
            "prose then bare json":
                'I will read it.\n{"tool": "read_file", "args": {"path": "x.py"}}',
            "nested braces in a value":
                '```tool_call\n{"tool": "patch_file", "args": {"path": "u.py", '
                '"search": "d = {\'a\': 1}", "replace": "d = {}"}}\n```',
            "block then trailing prose":
                '```tool_call\n{"tool": "read_file", "args": {"path": "x.py"}}\n```\n'
                'Then I will inspect it.',
        }
        for label, raw in shapes.items():
            with self.subTest(shape=label):
                self.assertIsNotNone(AgentLoop._parse_call(raw), label)

    def test_no_observation_ever_embeds_a_live_tool_call_fence(self) -> None:
        """A contract, because "remember next time" is not a mechanism.

        Measured: an observation carrying a real ```tool_call block made
        qwen3:8b spend 334.7s and return ZERO characters; the same guidance in
        prose got a correct parsed call in 42.4s. A model told to reply with
        exactly one such block, handed a prompt already containing one,
        produces nothing. Only the SYSTEM PROMPT may show the fence -- it
        defines the format; observations must describe calls in prose.
        """
        import inspect

        from saleha.core import agentic_loop as mod

        src = inspect.getsource(mod)
        # Strip the system prompt, which legitimately shows the format.
        without_prompt = src.replace(AgentLoop.SYSTEM_PROMPT, "")
        # The remaining source must not build a fence inside any string it
        # hands back to the model as an observation or rejection.
        self.assertNotIn('```tool_call\\n{"tool"', without_prompt)
        self.assertNotIn("```tool_call\\n{{\"tool\"", without_prompt)

        for hint in mod._NEXT_ACTION_HINT.values():
            self.assertNotIn("```", hint, f"live fence in hint: {hint!r}")

    def test_tool_observations_are_fence_free_on_real_files(self) -> None:
        agent = ScriptedAgent([_finish("x")])
        loop = AgentLoop(agent=agent, root_dir=self.root)
        big = os.path.join(self.root, "big.py")
        with open(big, "w", encoding="utf-8") as fh:
            fh.write("def a():\n    return 1\n" * 400)
        for observation in (
            loop._tool_read_file("big.py"),
            loop._tool_get_file_outline("big.py"),
            loop._tool_find_symbols("a"),
        ):
            self.assertNotIn("```tool_call", observation)

    def test_qwen3_real_reply_shapes_all_parse(self) -> None:
        """The four shapes qwen3:8b actually emitted, copied byte-for-byte.

        Measured before fixing: only the YAML one failed. JSON inside a
        ```python fence already parsed via the embedded-object scan, and
        name/arguments were already accepted -- my first diagnosis blamed the
        fence language and the key names, and measurement disproved both.
        """
        shapes = {
            "YAML inside a ```python fence": (
                '```python\n'
                'tool_call:\n'
                '  name: read_file\n'
                '  arguments: {"path": "src/requests/utils.py"}\n'
                '```'
            ),
            "JSON inside a ```python fence": (
                '```python\ntool_call\n{\n  "name": "read_file",\n'
                '  "arguments": {\n    "path": "src/requests/utils.py"\n  }\n}\n```'
            ),
            "same JSON, canonical fence": (
                '```tool_call\n{"name": "read_file", "arguments": '
                '{"path": "src/requests/utils.py"}}\n```'
            ),
            "same JSON, no fence": (
                '{"name": "read_file", "arguments": '
                '{"path": "src/requests/utils.py"}}'
            ),
        }
        for label, raw in shapes.items():
            with self.subTest(shape=label):
                parsed = AgentLoop._parse_call(raw)
                self.assertIsNotNone(parsed, f"rejected: {label}")
                self.assertEqual(parsed[0], "read_file")
                self.assertEqual(parsed[1]["path"], "src/requests/utils.py")

    def test_yaml_tool_call_without_arguments_still_names_the_tool(self) -> None:
        raw = '```python\ntool_call:\n  name: list_dir\n```'
        parsed = AgentLoop._parse_call(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[0], "list_dir")
        self.assertEqual(parsed[1], {})

    def test_read_file_line_range_returns_numbered_lines(self) -> None:
        agent = ScriptedAgent([_finish("x")])
        loop = AgentLoop(agent=agent, root_dir=self.root)
        out = loop._tool_read_file("app.py", start_line=1, end_line=2)
        self.assertIn("1: ", out)
        self.assertNotIn("3: ", out)

    def test_read_file_rejects_non_numeric_range(self) -> None:
        agent = ScriptedAgent([_finish("x")])
        loop = AgentLoop(agent=agent, root_dir=self.root)
        out = loop._tool_read_file("app.py", start_line="abc")
        self.assertIn("must be integers", out)

    def test_bad_args_observation_names_the_correct_arguments(self) -> None:
        agent = ScriptedAgent([
            _tool_call("find_symbols", file_path="app.py"),
            _tool_call("read_file", path="app.py"),
            _finish("ok"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("investigate")
        self.assertIn("symbol_name", res.steps[0].observation)

    def test_prompt_advertises_real_argument_names(self) -> None:
        # The prompt used to list bare tool names, so the model guessed args.
        for tool, sig in AgentLoop.TOOL_SIGNATURES.items():
            self.assertTrue(sig.startswith("{"), tool)
        self.assertIn("symbol_name", AgentLoop.TOOL_SIGNATURES["find_symbols"])
        self.assertIn("pattern", AgentLoop.TOOL_SIGNATURES["search_repo"])
        self.assertIn("search", AgentLoop.TOOL_SIGNATURES["patch_file"])

    def test_write_disabled_by_default(self) -> None:
        # A blocked write is a FAILED mutation, so the loop now rejects the
        # following finish rather than reporting success over an unchanged
        # repo. The extra turns are that rejection being exercised.
        agent = ScriptedAgent([
            _tool_call("write_file", path="new.py", content="x=1"),
            _tool_call("read_file", path="app.py"),
            _finish("investigated only"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root, max_steps=6).run("write something")
        self.assertFalse(os.path.exists(os.path.join(self.root, "new.py")))
        self.assertIn("BLOCKED", res.steps[0].observation)

    def test_write_with_allow_and_approval_writes(self) -> None:
        agent = ScriptedAgent([
            _tool_call("write_file", path="notes/new.py", content="x=1"),
            _finish("written"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root, allow_write=True)
        with patch_gate(approve_result=True):
            res = loop.run("write notes")
        self.assertTrue(res.success)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "notes", "new.py")))

    def test_on_event_streaming(self) -> None:
        events = []
        agent = ScriptedAgent([
            _tool_call("list_dir", path="."),
            _finish("listed"),
        ])
        AgentLoop(agent=agent, root_dir=self.root).run(
            "explore", on_event=events.append)
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[-1]["action"], "finish")

    def test_patch_file_tool(self) -> None:
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

    def test_get_file_outline_and_find_symbols(self) -> None:
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

    def test_outline_hint_points_at_the_goal_relevant_function_not_the_first(self) -> None:
        """Measured against a real repo bug: super_len() is what the goal
        names, but the file's first top-level function was an unrelated
        dict_to_sequence() earlier in the source. get_file_outline's hint
        (and the located_region it feeds) always pointed at whichever
        function happened to be first, not the one the goal is about --
        so a real qwen2.5-coder:3b run read the wrong function's body and
        never came near patch_file."""
        path = os.path.join(self.root, "utils.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                "def dict_to_sequence(d):\n    return d.items()\n\n\n"
                "def super_len(o):\n    return len(o)\n"
            )
        agent = ScriptedAgent([
            _tool_call("get_file_outline", path="utils.py"),
            _finish("inspected"),
        ])
        # allow_write left at its default (False) -- this test is only about
        # the outline hint itself, not the separate repair-goal mutation gate.
        loop = AgentLoop(agent=agent, root_dir=self.root, max_steps=3)
        res = loop.run("fix the bug in super_len() -- it returns the wrong value")
        obs = res.steps[0].observation
        # The hint must name super_len's own line range (5-6), not
        # dict_to_sequence's (1-2) just because it comes first in the file.
        hint_section = obs[obs.index("These are line numbers"):]
        self.assertNotIn("dict_to_sequence", hint_section)
        self.assertIn("super_len", hint_section)
        self.assertIn("start_line 5", hint_section)
        self.assertIn("end_line 6", hint_section)

    def test_outline_hint_falls_back_to_first_entry_when_goal_names_nothing(self) -> None:
        """A goal with no identifiable function name must not break --
        the original first-entry hint stands unchanged."""
        path = os.path.join(self.root, "utils.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write("def dict_to_sequence(d):\n    return d.items()\n")
        agent = ScriptedAgent([
            _tool_call("get_file_outline", path="utils.py"),
            _finish("inspected"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root)
        res = loop.run("clean up this file")
        self.assertIn("dict_to_sequence", res.steps[0].observation)

    def test_deepseek_r1_think_parsing(self) -> None:
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

    def test_premature_finish_rejected_then_recovers(self) -> None:
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

    def test_repeated_premature_finish_exhausts_max_steps(self) -> None:
        """If the model never takes a real action, it must not be able to
        force a false success by just repeating finish()."""
        agent = ScriptedAgent([_finish("done")] * 5)
        res = AgentLoop(agent=agent, root_dir=self.root, max_steps=3).run("do nothing")
        self.assertFalse(res.success)
        self.assertIn("max_steps", res.error)

    def test_min_actions_before_finish_zero_keeps_old_behavior(self) -> None:
        """min_actions_before_finish=0 restores immediate-finish (opt-out)."""
        agent = ScriptedAgent([_finish("instant")])
        res = AgentLoop(agent=agent, root_dir=self.root,
                         min_actions_before_finish=0).run("trivial goal")
        self.assertTrue(res.success)
        self.assertEqual(res.final_message, "instant")

    # ------------------------------------------------------------------
    # A repair goal is not done until something on disk changed
    # ------------------------------------------------------------------

    def test_repair_goal_cannot_finish_after_only_reading(self) -> None:
        """Measured against a real planted bug in psf/requests: the agent
        called list_dir once, called finish(), and the CLI printed a green
        "Agent Summary" over a byte-identical file whose 4 tests were still
        failing. The existing mutation gate only fires once a mutation has
        been ATTEMPTED and failed, so a run that never tried fell through."""
        agent = ScriptedAgent([
            _tool_call("list_dir", path="."),
            _finish("I have analyzed the code and fixed the bug."),
            _finish("The fix is complete."),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=3).run(
            "The test test_super_len_with_tell is failing. Fix the bug.")
        self.assertFalse(res.success, msg=res.final_message)

    def test_repair_goal_finishes_once_a_patch_lands(self) -> None:
        """The same gate must not block a run that really did change a file."""
        path = os.path.join(self.root, "m.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        agent = ScriptedAgent([
            _tool_call("patch_file", path="m.py", search="x = 1", replace="x = 2"),
            _finish("patched"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=3).run("fix the value in m.py")
        self.assertTrue(res.success, msg=res.error)
        with open(path, encoding="utf-8") as f:
            self.assertIn("x = 2", f.read())

    def test_investigative_goal_still_finishes_without_any_mutation(self) -> None:
        """Read-only goals are legitimate -- the gate is armed by repair
        verbs only, so 'find all X' must not be forced to edit a file."""
        agent = ScriptedAgent([
            _tool_call("list_dir", path="."),
            _finish("Found three endpoints without auth."),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=3).run(
            "find all API endpoints missing auth checks")
        self.assertTrue(res.success, msg=res.error)

    def test_read_only_streak_nudges_toward_acting(self) -> None:
        """Measured against a real repo bug (pass 88): after find_symbols/
        search_repo fixes let the agent reach the right file quickly, it
        then re-read the same two files five times (different line ranges,
        so repeat-detection never caught it) and never called patch_file.
        The nudge must appear once the streak crosses the threshold."""
        with open(os.path.join(self.root, "m.py"), "w") as f:
            f.write("x = 1\n")
        agent = ScriptedAgent([
            _tool_call("read_file", path="m.py"),
            _tool_call("read_file", path="m.py", start_line=1, end_line=1),
            _tool_call("list_dir", path="."),
            _tool_call("read_file", path="m.py", start_line=1, end_line=2),
            _finish("done"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=6).run("investigate m.py")
        nudged = [s for s in res.steps if "call patch_file now" in s.observation]
        self.assertEqual(len(nudged), 1, res.steps)
        self.assertEqual(nudged[0].step, 4)

    def test_read_only_streak_resets_on_mutation_attempt(self) -> None:
        """A patch_file attempt (even a failing one) must reset the streak,
        so a model that is actively trying is not scolded for reading
        again afterward."""
        with open(os.path.join(self.root, "m.py"), "w") as f:
            f.write("x = 1\n")
        agent = ScriptedAgent([
            _tool_call("read_file", path="m.py"),
            _tool_call("read_file", path="m.py", start_line=1, end_line=1),
            _tool_call("patch_file", path="m.py", search="x = 1", replace="x = 2"),
            _tool_call("read_file", path="m.py"),
            _tool_call("read_file", path="m.py", start_line=1, end_line=1),
            _finish("done"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=8).run("fix m.py")
        nudged = [s for s in res.steps if "call patch_file now" in s.observation]
        self.assertEqual(nudged, [])

    def _locate_then_read(self, count: int) -> list:
        """A find_symbols call (which sets located_region) followed by
        `count` further read-only calls, each with distinct arguments so
        repeat-detection does not interfere."""
        return [_tool_call("find_symbols", symbol_name="charge")] + [
            _tool_call("read_file", path="app.py", start_line=1, end_line=1 + i)
            for i in range(count)
        ]

    def test_read_only_tools_are_blocked_once_the_target_is_located(self) -> None:
        """Measured live (pass 90): the nudge fired exactly as designed
        (verified by instrumenting a real run) and the model called
        find_symbols anyway on the very next step. A suggestion alone does
        not change the next action, so past the threshold a read-only call
        must be refused outright, not merely discouraged."""
        agent = ScriptedAgent(
            self._locate_then_read(8) + [_finish("done")] * 20)
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=12).run("fix charge in app.py")
        blocked = [s for s in res.steps if s.action.endswith("-blocked")]
        self.assertTrue(blocked, res.steps)
        self.assertIn("REJECTED", blocked[0].observation)
        self.assertIn("was not run", blocked[0].observation)

    def test_blocked_read_only_call_does_not_reach_the_real_tool(self) -> None:
        """The call must be refused before the handler runs -- verified by
        pointing the blocked call at a file that does not exist. If the
        handler had run, the observation would say "no such file"."""
        agent = ScriptedAgent(
            self._locate_then_read(7)
            + [_tool_call("read_file", path="does_not_exist.py")]
            + [_finish("done")] * 20)
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=12).run("fix charge in app.py")
        blocked = [s for s in res.steps if s.action.endswith("-blocked")]
        self.assertTrue(blocked, res.steps)
        for step in blocked:
            self.assertNotIn("no such file", step.observation)

    def test_hard_gate_names_the_located_region(self) -> None:
        """The rejection must name the concrete file and line range the
        tools already reported, so the model has somewhere to aim."""
        agent = ScriptedAgent(
            self._locate_then_read(8) + [_finish("done")] * 20)
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=12).run("fix charge in app.py")
        blocked = [s for s in res.steps if s.action.endswith("-blocked")]
        self.assertTrue(blocked, res.steps)
        self.assertIn("app.py", blocked[0].observation)
        self.assertIn("lines", blocked[0].observation)

    def test_patching_a_test_file_is_rejected_for_a_repair_goal(self) -> None:
        """Measured live (pass 91): forced to act by the read-only gate,
        qwen3:8b patched tests/test_utils.py -- changing an unrelated
        assertion from `== 0` to `== 00` -- then called finish() claiming
        "The bug in the test was a missing value... It has been fixed."
        The loop reported success=True with the real bug untouched and 4
        tests still failing. Editing the test is not fixing the code."""
        os.makedirs(os.path.join(self.root, "tests"), exist_ok=True)
        with open(os.path.join(self.root, "tests", "test_charge.py"), "w") as f:
            f.write("def test_charge():\n    assert charge(1) == 2\n")
        agent = ScriptedAgent([
            _tool_call("patch_file", path="tests/test_charge.py",
                       search="== 2", replace="== 4"),
        ] + [_finish("done")] * 20)
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=4).run("fix the failing charge test")
        rejected = [s for s in res.steps
                    if s.action == "patch_file-rejected-test-file"]
        self.assertTrue(rejected, res.steps)
        self.assertIn("is a test file", rejected[0].observation)
        # The file must be byte-identical -- the tool never ran.
        with open(os.path.join(self.root, "tests", "test_charge.py")) as f:
            self.assertIn("== 2", f.read())

    def test_patching_source_is_still_allowed_for_a_repair_goal(self) -> None:
        """The test-file guard must not block the honest path."""
        agent = ScriptedAgent([
            _tool_call("patch_file", path="app.py",
                       search="amount * 2", replace="amount * 3"),
            _finish("patched the source"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=4).run("fix charge in app.py")
        self.assertTrue(res.success, res.error)
        with open(os.path.join(self.root, "app.py")) as f:
            self.assertIn("amount * 3", f.read())

    def test_test_file_guard_is_off_for_a_non_repair_goal(self) -> None:
        """Asked to *write* tests, editing a test file is the whole point."""
        os.makedirs(os.path.join(self.root, "tests"), exist_ok=True)
        with open(os.path.join(self.root, "tests", "test_charge.py"), "w") as f:
            f.write("def test_charge():\n    assert True\n")
        agent = ScriptedAgent([
            _tool_call("patch_file", path="tests/test_charge.py",
                       search="assert True", replace="assert charge(1) == 2"),
            _finish("extended the test"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=4).run("write a better assertion in the charge test")
        rejected = [s for s in res.steps
                    if s.action.endswith("-rejected-test-file")]
        self.assertEqual(rejected, [], res.steps)

    def test_hard_gate_stays_off_until_a_region_is_located(self) -> None:
        """Measured live (pass 90): with the block firing before the tools
        had located anything, qwen3:8b was forced to patch after reading
        only the *test* file -- it had not yet found the source at all, so
        all three forced patch_file calls targeted the wrong file and
        failed with "Could not match search block". Forcing action before
        the target is known is worse than one more read."""
        agent = ScriptedAgent(
            [_tool_call("read_file", path="app.py", start_line=1, end_line=1 + i)
             for i in range(10)] + [_finish("done")] * 20)
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                        max_steps=12).run("fix charge in app.py")
        blocked = [s for s in res.steps if s.action.endswith("-blocked")]
        self.assertEqual(blocked, [], "blocked before any region was located")

    def test_hard_gate_off_when_writes_are_not_allowed(self) -> None:
        """A read-only run cannot patch anything, so the hard gate must not
        block its investigation -- it would make the run permanently stuck
        with no legal tool left to call."""
        agent = ScriptedAgent([
            _tool_call("list_dir", path="."),
            _tool_call("list_dir", path="."),
            _tool_call("list_dir", path="."),
            _tool_call("list_dir", path="."),
            _tool_call("list_dir", path="."),
            _finish("investigated"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=False,
                        max_steps=8).run("find all endpoints missing auth")
        blocked = [s for s in res.steps if s.action.endswith("-blocked")]
        self.assertEqual(blocked, [])
        self.assertTrue(res.success)

    def test_repair_gate_is_off_when_writes_are_not_allowed(self) -> None:
        """A read-only run cannot mutate anything, so requiring a mutation
        would make it permanently unfinishable."""
        agent = ScriptedAgent([
            _tool_call("list_dir", path="."),
            _finish("Here is what I found and what would need to change."),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root, allow_write=False,
                        max_steps=3).run("fix the failing test")
        self.assertTrue(res.success, msg=res.error)

    # ------------------------------------------------------------------
    # Prompt size is budgeted per model, because a reasoning model's
    # <think> block competes with its answer for the same num_predict
    # ------------------------------------------------------------------

    def test_reasoning_model_gets_a_smaller_prompt_budget(self) -> None:
        """Measured (pass 86): qwen3:8b at a 10,356-char prompt returned an
        empty reply, done_reason='length' -- the whole budget went into
        thinking. The same model solved the same bug at 571 chars."""
        class _R(ScriptedAgent):
            model_preference = "qwen3:8b"

        loop = AgentLoop(agent=_R([]), root_dir=self.root)
        self.assertTrue(loop.is_reasoning)
        self.assertLess(loop.max_file_read_chars, MAX_FILE_READ_CHARS)
        self.assertLess(loop.max_observation_chars, MAX_OBSERVATION_CHARS)
        self.assertLess(loop.transcript_steps, 6)

    def test_non_reasoning_model_budgets_are_unchanged(self) -> None:
        """No prior measurement may shift: the 3b path keeps its old caps."""
        class _N(ScriptedAgent):
            model_preference = "qwen2.5-coder:3b"

        loop = AgentLoop(agent=_N([]), root_dir=self.root)
        self.assertFalse(loop.is_reasoning)
        self.assertEqual(loop.max_file_read_chars, MAX_FILE_READ_CHARS)
        self.assertEqual(loop.max_observation_chars, MAX_OBSERVATION_CHARS)
        self.assertEqual(loop.transcript_steps, 6)

    def test_reasoning_budget_actually_shrinks_a_file_read(self) -> None:
        """The cap has to reach the tool, not just sit on the instance."""
        big = "\n".join(f"line {i} " + "x" * 60 for i in range(400))
        self._write_root("big.py", big)

        class _R(ScriptedAgent):
            model_preference = "qwen3:8b"

        class _N(ScriptedAgent):
            model_preference = "qwen2.5-coder:3b"

        r_obs = AgentLoop(agent=_R([]), root_dir=self.root)._tool_read_file("big.py")
        n_obs = AgentLoop(agent=_N([]), root_dir=self.root)._tool_read_file("big.py")
        self.assertLess(len(r_obs), len(n_obs))

    def _write_root(self, name: str, text: str) -> None:
        with open(os.path.join(self.root, name), "w", encoding="utf-8") as f:
            f.write(text)

    # ------------------------------------------------------------------
    # Parse resilience: one bad reply must not kill the whole run
    # ------------------------------------------------------------------

    def test_prose_only_turn_is_retried_not_fatal(self) -> None:
        """Real measured failure: qwen2.5-coder:3b's first turn is often pure
        prose ("I will start by listing all files...") with the tool call
        intended for the next turn. That single turn used to end the run at
        step 1 -- the real cause of the earlier 0/3 SWE-bench result."""
        agent = ScriptedAgent([
            "To find the bug, I will start by listing all the files.",
            _tool_call("read_file", path="app.py"),
            _finish("found it"),
        ])
        events = []
        res = AgentLoop(agent=agent, root_dir=self.root).run(
            "find the bug", on_event=events.append)
        self.assertTrue(res.success, res.error)
        self.assertEqual(res.final_message, "found it")
        retries = [e for e in events if e.get("action") == "parse-retry"]
        self.assertEqual(len(retries), 1)
        # The prose turn produced no step; only the real tool call did.
        self.assertEqual(res.steps[0].action, "read_file")

    def test_gives_up_after_consecutive_unparseable_replies(self) -> None:
        """Resilience must not become an infinite tolerance for garbage."""
        agent = ScriptedAgent(["just talking, no block"] * 8)
        res = AgentLoop(agent=agent, root_dir=self.root,
                        max_parse_retries=3, max_steps=10).run("do something")
        self.assertFalse(res.success)
        self.assertIn("consecutive replies", res.error)

    def test_parse_failure_streak_resets_on_a_good_reply(self) -> None:
        """Only CONSECUTIVE failures should end the run."""
        agent = ScriptedAgent([
            "prose 1",
            _tool_call("list_dir", path="."),   # resets the streak
            "prose 2",
            "prose 3",
            _tool_call("read_file", path="app.py"),
            _finish("done"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root,
                        max_parse_retries=2, max_steps=10).run("investigate")
        self.assertTrue(res.success, res.error)
        self.assertEqual(len(res.steps), 3)  # list_dir + read_file + finish

    def test_max_parse_retries_zero_restores_fail_fast(self) -> None:
        agent = ScriptedAgent(["no block here", _tool_call("list_dir", path=".")])
        res = AgentLoop(agent=agent, root_dir=self.root,
                        max_parse_retries=0).run("go")
        self.assertFalse(res.success)
        self.assertIn("no tool_call/finish block", res.error)

    def test_parses_bare_json_call_embedded_in_prose(self) -> None:
        """The model explains itself, then emits an unfenced JSON object."""
        agent = ScriptedAgent([
            'I will read the file first.\n{"tool": "read_file", "args": {"path": "app.py"}}',
            _finish("read it"),
        ])
        res = AgentLoop(agent=agent, root_dir=self.root).run("read app.py")
        self.assertTrue(res.success, res.error)
        self.assertEqual(res.steps[0].action, "read_file")
        self.assertIn("def charge", res.steps[0].observation)

    def test_parse_retry_does_not_leave_evidence_ledger_inconsistent(self) -> None:
        from saleha.core.task_evidence import EvidenceKind, TaskState
        agent = ScriptedAgent(["all prose"] * 5)
        loop = AgentLoop(agent=agent, root_dir=self.root, max_parse_retries=2,
                         require_evidence=True,
                         required_evidence={EvidenceKind.FILE_READ})
        res = loop.run("go")
        self.assertFalse(res.success)
        assert loop.ledger is not None
        self.assertEqual(loop.ledger.state, TaskState.FAILED)

    # ------------------------------------------------------------------
    # Evidence-based completion (Level-6 architecture target)
    # ------------------------------------------------------------------

    def test_evidence_gate_rejects_finish_with_no_real_work(self) -> None:
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
        assert loop.ledger is not None
        self.assertEqual(loop.ledger.state, TaskState.ACCEPTED)
        self.assertTrue(loop.ledger.has(EvidenceKind.FILE_READ))

    def test_evidence_gate_never_accepts_without_the_required_kind(self) -> None:
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
        assert loop.ledger is not None
        self.assertEqual(loop.ledger.state, TaskState.FAILED)

    def test_failed_tool_call_produces_no_evidence(self) -> None:
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
        assert loop.ledger is not None
        # Exactly one FILE_READ evidence -- from the successful call only.
        reads = [e for e in loop.ledger.evidence if e.kind == EvidenceKind.FILE_READ]
        self.assertEqual(len(reads), 1)

    def test_write_evidence_moves_state_to_implementing(self) -> None:
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
        assert loop.ledger is not None
        self.assertTrue(loop.ledger.has(EvidenceKind.FILE_MODIFIED))
        states = [h["state"] for h in loop.ledger.history]
        self.assertIn("IMPLEMENTING", states)
        self.assertEqual(loop.ledger.state, TaskState.ACCEPTED)

    def test_budget_stops_a_runaway_loop(self) -> None:
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
        assert loop.ledger is not None
        self.assertEqual(loop.ledger.state, TaskState.FAILED)
        self.assertEqual(len(res.steps), 4)  # 3 allowed, 4th trips the limit

    def test_evidence_off_by_default_keeps_old_behaviour(self) -> None:
        """Existing callers must be unaffected: no ledger, no gate."""
        agent = ScriptedAgent([
            _tool_call("read_file", path="app.py"),
            _finish("done"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root)
        res = loop.run("understand billing")
        self.assertTrue(res.success, res.error)
        self.assertIsNone(loop.ledger)

    def test_structured_xml_tool_call_and_thinking_parsing(self) -> None:
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


class RunTestsToolTests(unittest.TestCase):
    """The run_tests tool and the evidence gate that depends on it.

    EvidenceKind.TESTS_PASSED existed since the ledger was written, but no
    tool could record it -- so a completion claim could never rest on an
    actual test run. Measured against a real `requests` bug in pass 53: the
    agent landed two patches, reported success, and took the repo from 4
    failing tests to 7, because "did a write succeed?" was the only question
    being asked.
    """

    def setUp(self) -> None:
        # These tests run a real nested pytest inside the temp dir, which
        # leaves __pycache__/*.pyc files the OS may still hold open when
        # tearDown runs. On Windows that makes cleanup raise WinError 32
        # and fails the test *after* its assertions have already passed --
        # a red suite caused by teardown, not by the code under test.
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _loop(self, **kw: Any) -> AgentLoop:
        return AgentLoop(agent=ScriptedAgent([]), root_dir=self.root, **kw)

    def _write(self, name: str, text: str) -> None:
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    # ---- discovery -------------------------------------------------
    def test_discovery_reports_why_when_nothing_is_found(self) -> None:
        """An empty directory must say so, not fall back to a command that
        tests nothing and exits 0."""
        argv, why = self._loop()._discover_test_command()
        self.assertIsNone(argv)
        self.assertIn("none found", why)

    def test_discovery_finds_pytest_from_pyproject(self) -> None:
        self._write("pyproject.toml", "[tool.pytest.ini_options]\ntestpaths = ['t']\n")
        argv, why = self._loop()._discover_test_command()
        self.assertIsNotNone(argv)
        assert argv is not None
        self.assertIn("pytest", argv)
        self.assertIn("pyproject.toml", why)

    def test_discovery_finds_cargo_from_manifest(self) -> None:
        self._write("Cargo.toml", "[package]\nname = 'x'\n")
        argv, _ = self._loop()._discover_test_command()
        self.assertEqual(argv, ["cargo", "test"])

    def test_discovery_ignores_package_json_without_a_test_script(self) -> None:
        """A marker's presence is not the same as it configuring tests."""
        self._write("package.json", '{"name": "x", "scripts": {"build": "tsc"}}')
        argv, why = self._loop()._discover_test_command()
        self.assertIsNone(argv)
        self.assertIn("none found", why)

    def test_discovery_falls_back_to_a_tests_directory(self) -> None:
        self._write("tests/test_x.py", "def test_ok():\n    assert True\n")
        argv, why = self._loop()._discover_test_command()
        self.assertIsNotNone(argv)
        assert argv is not None
        self.assertIn("pytest", argv)
        self.assertIn("tests/", why)

    # ---- running ---------------------------------------------------
    def test_missing_test_command_is_reported_not_faked(self) -> None:
        observation = self._loop()._tool_run_tests()
        self.assertTrue(observation.startswith("no test command found:"))
        self.assertFalse(observation.startswith("PASSED "))

    def test_a_passing_suite_reports_passed(self) -> None:
        self._write("pyproject.toml", "[tool.pytest.ini_options]\n")
        self._write("test_ok.py", "def test_ok():\n    assert True\n")
        observation = self._loop()._tool_run_tests(target="test_ok.py")
        self.assertTrue(observation.startswith("PASSED "), msg=observation)
        self.assertIn("exit 0", observation)

    def test_a_failing_suite_reports_failed(self) -> None:
        self._write("pyproject.toml", "[tool.pytest.ini_options]\n")
        self._write("test_bad.py", "def test_bad():\n    assert False\n")
        observation = self._loop()._tool_run_tests(target="test_bad.py")
        self.assertTrue(observation.startswith("FAILED "), msg=observation)
        self.assertFalse(observation.startswith("PASSED "))

    def test_target_cannot_escape_the_repo_root(self) -> None:
        self._write("pyproject.toml", "[tool.pytest.ini_options]\n")
        observation = self._loop()._tool_run_tests(target="../../etc/passwd")
        self.assertIn("path traversal blocked", observation)

    # ---- the evidence gate -----------------------------------------
    def _run_with_evidence(self, script: list) -> LoopResult:
        from saleha.core.task_evidence import EvidenceKind

        loop = AgentLoop(
            agent=ScriptedAgent(script),
            root_dir=self.root,
            require_evidence=True,
            required_evidence=[EvidenceKind.TESTS_PASSED],
            min_actions_before_finish=0,
            max_steps=4,
        )
        return loop.run("make the suite green")

    def test_a_passing_run_records_tests_passed_and_admits_finish(self) -> None:
        self._write("pyproject.toml", "[tool.pytest.ini_options]\n")
        self._write("test_ok.py", "def test_ok():\n    assert True\n")
        result = self._run_with_evidence([
            _tool_call("run_tests", target="test_ok.py"),
            _finish("suite is green"),
        ])
        self.assertTrue(result.success, msg=result.error)

    def test_a_failing_run_records_nothing_so_finish_is_refused(self) -> None:
        """The one tool whose call succeeding is NOT the fact being claimed:
        run_tests runs fine and reports a red suite. Recording TESTS_PASSED
        there would be exactly the fake green this tool exists to prevent."""
        self._write("pyproject.toml", "[tool.pytest.ini_options]\n")
        self._write("test_bad.py", "def test_bad():\n    assert False\n")
        result = self._run_with_evidence([
            _tool_call("run_tests", target="test_bad.py"),
            _finish("all fixed"),
            _finish("really, all fixed"),
            _finish("please"),
        ])
        self.assertFalse(result.success)
        rejected = [s for s in result.steps if "REJECTED" in s.observation]
        self.assertTrue(
            rejected or "max_steps" in result.error,
            msg=f"finish should never be admitted on a red suite: {result.error}",
        )

    def test_the_prompt_advertises_run_tests(self) -> None:
        self.assertIn("run_tests", AgentLoop.TOOL_SIGNATURES)
        self._write("pyproject.toml", "[tool.pytest.ini_options]\n")
        agent = ScriptedAgent([_finish("x")])
        loop = AgentLoop(agent=agent, root_dir=self.root,
                         min_actions_before_finish=0, max_steps=1)
        loop.run("anything")
        self.assertIn("run_tests", agent.prompts[0])

    # ---- the AUTOMATIC verification gate ----------------------------
    # Measured live against the planted requests bug (pass 92-adjacent):
    # qwen3:8b navigated correctly, patch_file reported "successfully
    # patched", and finish() claimed the bug was fixed -- but the edit
    # landed on the wrong line and the real suite went 4 failed -> 6
    # failed. require_evidence defaults off and no production caller
    # (saleha agent, swe_bench_runner) turns it on, so the ledger tests
    # above had never once exercised a live repair run. These tests do
    # NOT set require_evidence -- they use the loop the way `saleha
    # agent` actually constructs it, so the gate under test is the one
    # that runs automatically regardless of that flag.

    def test_a_wrong_patch_is_caught_by_an_automatic_test_run(self) -> None:
        """The tool reporting "successfully patched" is not proof the fix
        is correct. The loop must run the real suite itself and refuse
        finish() on a red result, without the model ever calling
        run_tests or require_evidence being set."""
        self._write("pyproject.toml", "[tool.pytest.ini_options]\n")
        self._write("calc.py", "def double(x):\n    return x\n")
        self._write("test_calc.py",
                    "from calc import double\n"
                    "def test_double():\n"
                    "    assert double(3) == 6\n")
        agent = ScriptedAgent([
            _tool_call("patch_file", path="calc.py",
                      search="return x", replace="return x + 1"),
            _finish("fixed double() to return the doubled value"),
            _finish("really, it is fixed"),
        ])
        result = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                           max_steps=3).run("fix the bug in double()")
        self.assertFalse(result.success, msg=result.final_message)
        rejected = [s for s in result.steps if "REJECTED" in s.observation]
        self.assertTrue(rejected, msg=result.steps)
        self.assertIn("test suite says otherwise", rejected[-1].observation)
        with open(os.path.join(self.root, "calc.py"), encoding="utf-8") as f:
            self.assertIn("return x + 1", f.read(),
                          msg="the wrong patch really did land on disk")

    def test_finish_stays_hidden_after_a_verified_wrong_patch(self) -> None:
        """Measured live (pass 95): rejected with the real failing pytest
        output embedded and told "patch_file again with a corrected fix",
        qwen2.5-coder:3b replied finish() anyway on the very next turn --
        seven times in a row, never touching patch_file again. Probed in
        isolation with the identical transcript: the same rejection as
        prose text did not stop it; removing finish() from the prompt did.
        Once auto-verify has recorded a failing verdict, finish() must not
        reappear in the prompt until a new mutation is attempted."""
        self._write("pyproject.toml", "[tool.pytest.ini_options]\n")
        self._write("calc.py", "def double(x):\n    return x\n")
        self._write("test_calc.py",
                    "from calc import double\n"
                    "def test_double():\n"
                    "    assert double(3) == 6\n")
        agent = ScriptedAgent([
            _tool_call("patch_file", path="calc.py",
                      search="return x", replace="return x + 1"),
            _finish("fixed"),
            _finish("really, it is fixed"),
            _finish("no really"),
        ])
        AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                 max_steps=4).run("fix the bug in double()")
        # prompts[0]: before any mutation -- finish() hidden (pass-95 gate).
        # prompts[1]: right after the patch, before auto-verify has run --
        # finish() correctly offered (mutations_attempted >= 1, no verdict
        # yet), the model uses it and gets rejected by auto-verify.
        # prompts[2..]: AFTER auto-verify recorded a failing verdict -- must
        # STAY hidden, not re-armed just because a mutation was attempted.
        self.assertIn('"finish"', agent.prompts[1])
        for i, p in enumerate(agent.prompts[2:], start=2):
            self.assertNotIn('"finish"', p, msg=f"prompt {i} offered finish()")

    def test_a_correct_patch_passes_the_automatic_test_run(self) -> None:
        """The gate must not block a genuinely correct fix."""
        self._write("pyproject.toml", "[tool.pytest.ini_options]\n")
        self._write("calc.py", "def double(x):\n    return x\n")
        self._write("test_calc.py",
                    "from calc import double\n"
                    "def test_double():\n"
                    "    assert double(3) == 6\n")
        agent = ScriptedAgent([
            _tool_call("patch_file", path="calc.py",
                      search="return x", replace="return x * 2"),
            _finish("fixed double() to actually double"),
        ])
        result = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                           max_steps=3).run("fix the bug in double()")
        self.assertTrue(result.success, msg=result.error)

    def test_no_discoverable_test_command_does_not_block_finish(self) -> None:
        """A repo this loop cannot test must not fail a repair for that
        reason -- there is nothing to verify against, so the gate stays
        out of the way rather than rejecting on a technicality."""
        self._write("calc.py", "def double(x):\n    return x\n")
        agent = ScriptedAgent([
            _tool_call("patch_file", path="calc.py",
                      search="return x", replace="return x * 2"),
            _finish("fixed double() to actually double"),
        ])
        result = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                           max_steps=3).run("fix the bug in double()")
        self.assertTrue(result.success, msg=result.error)

    def test_verification_is_not_re_run_on_a_repeated_finish_attempt(self) -> None:
        """Once verified for the current file state, a second finish()
        attempt (e.g. after being rejected for an unrelated reason) must
        not re-run the whole suite again -- only a NEW mutation should
        invalidate the cached verdict."""
        self._write("pyproject.toml", "[tool.pytest.ini_options]\n")
        self._write("calc.py", "def double(x):\n    return x\n")
        self._write("test_calc.py",
                    "from calc import double\n"
                    "def test_double():\n"
                    "    assert double(3) == 6\n")
        agent = ScriptedAgent([
            _tool_call("patch_file", path="calc.py",
                      search="return x", replace="return x * 2"),
            _finish("fixed"),
        ])
        result = AgentLoop(agent=agent, root_dir=self.root, allow_write=True,
                           max_steps=3).run("fix the bug in double()")
        self.assertTrue(result.success, msg=result.error)
        verify_steps = [s for s in result.steps if s.action == "auto-verify-tests"]
        self.assertEqual(len(verify_steps), 1, result.steps)


class patch_gate:
    """Context manager that forces approval_gate.approve to return a fixed boolean."""
    def __init__(self, approve_result: bool = True) -> None:
        self.result = approve_result
        self._cm = None

    def __enter__(self) -> "patch_gate":
        from unittest.mock import patch
        import saleha.core.approval_gate as gate
        self._cm = patch.object(gate, "approve",
                                lambda *a, **k: self.result)
        self._cm.__enter__()
        # agentic_loop performs function-local import -- module attribute is patched
        import saleha.core.approval_gate as gate2
        assert callable(gate2.approve)
        return self

    def __exit__(self, *a: Any) -> Optional[bool]:
        if self._cm is not None:
            return self._cm.__exit__(*a)
        return None


class AutonomousSelfBuildingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_dynamic_registry_tool_invocation(self) -> None:
        from saleha.tools.base import BaseTool, ToolResult, tool_registry

        class MockEchoTool(BaseTool):
            name = "mock_echo"
            description = "Echoes back the message"
            parameters = {
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            }

            def execute(self, **kwargs: Any) -> ToolResult:
                return ToolResult(success=True, data={"echo": kwargs.get("msg", "")})

        tool_registry.register(MockEchoTool())

        agent = ScriptedAgent([
            _tool_call("mock_echo", msg="hello world"),
            _finish("echo verified"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root)
        res = loop.run("test echo tool")
        self.assertTrue(res.success, msg=res.error)
        self.assertEqual(res.steps[0].action, "mock_echo")
        self.assertIn("hello world", res.steps[0].observation)

    def test_forge_tool_blocked_when_write_disabled(self) -> None:
        agent = ScriptedAgent([
            _tool_call("forge_tool", name="dummy_calc", description="Performs calculations"),
            _finish("done"),
        ])
        loop = AgentLoop(agent=agent, root_dir=self.root, allow_write=False)
        res = loop.run("forge dummy tool")
        self.assertEqual(res.steps[0].action, "forge_tool")
        self.assertIn("BLOCKED: forge_tool disabled", res.steps[0].observation)

    def test_forge_tool_blocked_when_approval_denied(self) -> None:
        agent = ScriptedAgent([
            _tool_call("forge_tool", name="dummy_calc", description="Performs calculations"),
            _finish("done"),
        ])
        with patch_gate(approve_result=False):
            loop = AgentLoop(agent=agent, root_dir=self.root, allow_write=True)
            res = loop.run("forge dummy tool")
            self.assertEqual(res.steps[0].action, "forge_tool")
            self.assertIn("BLOCKED: human approval denied", res.steps[0].observation)

    def test_forge_tool_success_and_immediate_invocation_turn(self) -> None:
        from unittest.mock import patch
        from saleha.core.tool_forge import ToolForgeResult
        from saleha.tools.base import BaseTool, ToolResult, tool_registry

        class MockForgedTool(BaseTool):
            name = "synthesized_calculator"
            description = "Calculates sums"
            parameters = {"type": "object", "properties": {"val": {"type": "integer"}}}

            def execute(self, **kwargs: Any) -> ToolResult:
                return ToolResult(success=True, data={"result": kwargs.get("val", 0) * 10})

        mock_forge_res = ToolForgeResult(
            timestamp="2026-09-21 00:00:00",
            tool_name="synthesized_calculator",
            status="created",
            detail="Synthesized mock tool successfully",
            tool_path="saleha/tools/synthesized_calculator.py",
            tests_passed=True,
        )

        with patch_gate(approve_result=True), \
             patch("saleha.core.tool_forge.ToolForge.forge_tool", return_value=mock_forge_res):
            tool_registry.register(MockForgedTool())

            agent = ScriptedAgent([
                _tool_call("forge_tool", name="synthesized_calculator", description="Calculates sums"),
                _tool_call("synthesized_calculator", val=5),
                _finish("tool forged and executed"),
            ])
            loop = AgentLoop(agent=agent, root_dir=self.root, allow_write=True, max_steps=4)
            res = loop.run("create and run calculator")
            self.assertTrue(res.success, msg=res.error)
            self.assertEqual(res.steps[0].action, "forge_tool")
            self.assertIn("successfully forged", res.steps[0].observation)
            self.assertEqual(res.steps[1].action, "synthesized_calculator")
            self.assertIn('"result": 50', res.steps[1].observation)


if __name__ == "__main__":
    unittest.main()
