import unittest
import os
import tempfile
import json
import sqlite3
from click.testing import CliRunner

from saleha.core.tool_calling import (
    ToolRegistry, ToolDefinition, ToolParameter,
    ToolCallingLoop, global_tool_registry
)
from saleha.cli.commands import cli


class ToolCallingTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()

    def test_custom_tool_registration_and_schema(self):
        def my_adder(a: int, b: int) -> int:
            return a + b

        tool_def = ToolDefinition(
            name="add_numbers",
            description="Adds two integers.",
            parameters=[
                ToolParameter("a", "integer", "First number", required=True),
                ToolParameter("b", "integer", "Second number", required=True),
            ],
            handler=my_adder
        )
        self.registry.register(tool_def)
        schema = tool_def.to_json_schema()

        self.assertEqual(schema["name"], "add_numbers")
        self.assertIn("a", schema["parameters"]["properties"])
        self.assertIn("b", schema["parameters"]["properties"])
        self.assertEqual(schema["parameters"]["required"], ["a", "b"])

        res = self.registry.execute("add_numbers", a=10, b=25)
        self.assertTrue(res.success)
        self.assertEqual(res.output, "35")

    def test_sqlite_inspect_builtin_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);")
            cursor.execute("INSERT INTO users (username) VALUES ('saleha_dev');")
            conn.commit()
            conn.close()

            # Test schema inspect
            res_schema = self.registry.execute("sqlite_inspect", db_path=db_path)
            self.assertTrue(res_schema.success)
            self.assertIn("CREATE TABLE users", res_schema.output)

            # Test read-only SELECT
            res_query = self.registry.execute("sqlite_inspect", db_path=db_path, query="SELECT * FROM users;")
            self.assertTrue(res_query.success)
            self.assertIn("saleha_dev", res_query.output)

            # Test blocking write queries
            res_blocked = self.registry.execute("sqlite_inspect", db_path=db_path, query="DROP TABLE users;")
            self.assertIn("Only read-only queries", res_blocked.output)

    def test_file_search_builtin_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "code.py")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("SECRET_KEY_PATTERN = '12345'\n")

            res = self.registry.execute("file_search", pattern="SECRET_KEY_PATTERN", search_path=tmpdir)
            self.assertTrue(res.success)
            self.assertIn("SECRET_KEY_PATTERN", res.output)

    def test_tool_calling_loop_parser(self):
        loop = ToolCallingLoop(self.registry)
        sample_response = """
I need to check the files first.
```tool_call
{
    "tool": "file_search",
    "args": {
        "pattern": "def hello",
        "search_path": "."
    }
}
```
"""
        call = loop.parse_tool_call(sample_response)
        self.assertIsNotNone(call)
        self.assertEqual(call.tool_name, "file_search")
        self.assertEqual(call.arguments.get("pattern"), "def hello")

    def test_cli_tools_json(self):
        res = CliRunner().invoke(cli, ["tools", "--json"])
        self.assertEqual(res.exit_code, 0)
        payload = json.loads(res.output)
        self.assertIn("tools", payload)
        tool_names = [t["name"] for t in payload["tools"]]
        self.assertIn("web_fetch", tool_names)
        self.assertIn("file_search", tool_names)
        self.assertIn("sqlite_inspect", tool_names)
        self.assertIn("shell_exec", tool_names)


if __name__ == "__main__":
    unittest.main()

