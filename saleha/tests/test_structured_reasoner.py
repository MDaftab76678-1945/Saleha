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


if __name__ == "__main__":
    unittest.main()
