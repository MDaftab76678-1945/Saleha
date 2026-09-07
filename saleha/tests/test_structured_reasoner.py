"""
Unit tests for Saleha Structured Reasoning & XML Tool Calling Engine.
"""

import unittest
from saleha.core.structured_reasoner import StructuredReasoner, structured_reasoner
from saleha.core.tool_calling import ToolDispatcher, ToolCall


class TestStructuredReasoner(unittest.TestCase):
    def test_parse_thinking_and_clean_response(self):
        text = """
<THINKING>
1. We need to inspect auth.py.
2. Check token expiration logic.
</THINKING>
I will now inspect the auth.py file for any security flaws.
"""
        turn = structured_reasoner.parse_turn(text)
        self.assertIn("inspect auth.py", turn.thinking)
        self.assertIn("inspect the auth.py file", turn.clean_response)
        self.assertNotIn("<THINKING>", turn.clean_response)

    def test_parse_scratchpad_variant(self):
        text = """
<scratchpad>
Step A: analyze AST.
</scratchpad>
Done analyzing.
"""
        turn = structured_reasoner.parse_turn(text)
        self.assertEqual(turn.thinking, "Step A: analyze AST.")
        self.assertEqual(turn.clean_response, "Done analyzing.")

    def test_parse_tool_call_json_style(self):
        text = """
<tool_call>
{"name": "read_file", "arguments": {"path": "src/main.py"}}
</tool_call>
"""
        turn = structured_reasoner.parse_turn(text)
        self.assertEqual(len(turn.tool_calls), 1)
        self.assertEqual(turn.tool_calls[0].name, "read_file")
        self.assertEqual(turn.tool_calls[0].arguments, {"path": "src/main.py"})

    def test_parse_tool_call_xml_tags_style(self):
        text = """
<tool_call>
<name>write_file</name>
<arguments>{"path": "test.txt", "content": "hello"}</arguments>
</tool_call>
"""
        turn = structured_reasoner.parse_turn(text)
        self.assertEqual(len(turn.tool_calls), 1)
        self.assertEqual(turn.tool_calls[0].name, "write_file")
        self.assertEqual(turn.tool_calls[0].arguments["content"], "hello")

    def test_parse_citations(self):
        text = 'Verified according to <co file="auth.py" line="42">def verify_token(): pass</co>.'
        turn = structured_reasoner.parse_turn(text)
        self.assertEqual(len(turn.citations), 1)
        self.assertEqual(turn.citations[0].file_path, "auth.py")
        self.assertEqual(turn.citations[0].line_number, 42)
        self.assertEqual(turn.citations[0].content, "def verify_token(): pass")

    def test_dispatcher_parses_structured_tool_call(self):
        dispatcher = ToolDispatcher()
        text = """
<THINKING>Let us read config.</THINKING>
<tool_call>
{"name": "read_file", "arguments": {"path": "settings.json"}}
</tool_call>
"""
        call = dispatcher.parse_tool_call(text)
        self.assertIsNotNone(call)
        self.assertEqual(call.tool_name, "read_file")
        self.assertEqual(call.arguments, {"path": "settings.json"})

    def test_format_system_prompt_and_tool_response(self):
        prompt = structured_reasoner.format_system_prompt_with_tools("Base Assistant", [{"name": "read_file"}])
        self.assertIn("<tools>", prompt)
        self.assertIn("<THINKING>", prompt)

        resp = structured_reasoner.format_tool_response("read_file", {"lines": 20})
        self.assertIn("<tool_response>", resp)
        self.assertIn('"lines": 20', resp)


class TruncatedReasoningTests(unittest.TestCase):
    """
    Reasoning models open <think> and can stop mid-thought when they hit a
    token budget or a timeout, so the closing tag never arrives.

    Every stripper in this repo matched paired tags only, which meant a
    truncated trace -- often thousands of tokens -- flowed on untouched as if
    it were the answer. Measured on this repo's own benchmark: the tag stayed
    in the extracted code and the task failed with a SyntaxError, recorded as
    a model failure. It was not one.
    """

    def test_closed_block_is_stripped(self):
        out = StructuredReasoner.strip_reasoning(
            "<think>reasoning here</think>\ndef solve():\n    return 1\n")
        self.assertNotIn("think", out.lower())
        self.assertIn("def solve", out)

    def test_truncated_block_is_stripped(self):
        """The regression this class exists for."""
        out = StructuredReasoner.strip_reasoning("<think>reasoning never finished")
        self.assertNotIn("think", out.lower())

    def test_truncated_block_does_not_leak_into_code(self):
        reply = "<think>I should write a function\ndef solve():\n    return 1\n"
        self.assertNotIn("<think>", StructuredReasoner.strip_reasoning(reply))

    def test_every_tag_spelling_is_handled_open_or_closed(self):
        for tag in ("think", "THINKING", "thinking", "SCRATCHPAD", "scratchpad"):
            with self.subTest(tag=tag, closed=True):
                text = "<{0}>x</{0}>\ncode".format(tag)
                self.assertNotIn(
                    tag.lower(),
                    StructuredReasoner.strip_reasoning(text).lower())
            with self.subTest(tag=tag, closed=False):
                text = "<{0}>x never closed".format(tag)
                self.assertNotIn(
                    tag.lower(),
                    StructuredReasoner.strip_reasoning(text).lower())

    def test_text_without_tags_is_untouched(self):
        code = "def solve():\n    return 1"
        self.assertEqual(StructuredReasoner.strip_reasoning(code), code)

    def test_empty_input(self):
        self.assertEqual(StructuredReasoner.strip_reasoning(""), "")
        self.assertEqual(StructuredReasoner.extract_reasoning(""), "")

    def test_reasoning_is_recoverable_from_both_shapes(self):
        self.assertEqual(
            StructuredReasoner.extract_reasoning("<think>my reasoning</think>code"),
            "my reasoning")
        self.assertEqual(
            StructuredReasoner.extract_reasoning("<think>my truncated reasoning"),
            "my truncated reasoning")

    def test_agentic_loop_uses_the_shared_stripper(self):
        """
        agentic_loop.py carried its own three re.sub calls, all paired-only.
        Duplicated stripping is how one copy gets fixed and the other does
        not, so the loop must route through this module.
        """
        import ast
        from pathlib import Path

        import saleha.core.agentic_loop as loop_module

        source = Path(loop_module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    docstrings.add(doc)
        literals = "\n".join(
            n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value not in docstrings)
        self.assertNotIn(
            "</think>", literals,
            "agentic_loop has its own paired-tag regex again; use "
            "StructuredReasoner.strip_reasoning instead")

