"""Tier C tests: MultiFileEditor (atomic/rollback/traversal) + multi-language."""
import io
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from saleha.core.multi_file_editor import MultiFileEditor
from saleha.agents.coder import CoderAgent


def _coder_returning(payload: str):
    coder = MagicMock()
    resp = MagicMock()
    resp.success = True
    resp.content = payload
    coder.think.return_value = resp
    return coder


VALID_TWO_FILES = """Here is the plan:
```json
{"edits": [
  {"path": "src/new_mod.py", "action": "create",
   "content": "def hello():\\n    return 'hi'\\n"},
  {"path": "README.md", "action": "create",
   "content": "# Demo\\n"}
]}
```"""


class MultiFileEditorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _path(self, rel):
        return os.path.join(self.root, rel)

    def test_dry_run_writes_nothing_but_parses_plan(self):
        coder = _coder_returning(VALID_TWO_FILES)
        ed = MultiFileEditor(coder_agent=coder, root_dir=self.root)
        res = ed.edit("add greeting module", apply=False)
        self.assertTrue(res.success, res.errors)
        self.assertEqual(len(res.edits), 2)
        self.assertFalse(res.applied)
        self.assertFalse(os.path.exists(self._path("src/new_mod.py")))

    def test_apply_creates_files_atomically(self):
        coder = _coder_returning(VALID_TWO_FILES)
        ed = MultiFileEditor(coder_agent=coder, root_dir=self.root)
        res = ed.edit("add files", apply=True)
        self.assertTrue(res.success, res.errors)
        self.assertTrue(res.applied)
        with open(self._path("src/new_mod.py"), encoding="utf-8") as f:
            self.assertIn("def hello", f.read())
        self.assertTrue(os.path.isfile(self._path("README.md")))

    def test_edit_existing_file_updates_content(self):
        os.makedirs(self._path("src"))
        with open(self._path("src/app.py"), "w", encoding="utf-8") as f:
            f.write("old = 1\n")
        payload = '''```json
{"edits": [{"path": "src/app.py", "action": "edit", "content": "old = 2\\n"}]}
```'''
        coder = _coder_returning(payload)
        ed = MultiFileEditor(coder_agent=coder, root_dir=self.root)
        res = ed.edit("bump version", apply=True)
        self.assertTrue(res.success, res.errors)
        with open(self._path("src/app.py"), encoding="utf-8") as f:
            self.assertIn("old = 2", f.read())

    def test_rollback_on_midway_failure(self):
        # pehli file theek, dusri ka target ek DIRECTORY hai -> write fail
        os.makedirs(self._path("blocked_dir"))
        payload = '''```json
{"edits": [
  {"path": "first_ok.py", "action": "create", "content": "x = 1\\n"},
  {"path": "blocked_dir", "action": "create", "content": "y = 2\\n"}
]}
```'''
        coder = _coder_returning(payload)
        ed = MultiFileEditor(coder_agent=coder, root_dir=self.root)
        res = ed.edit("two files", apply=True)
        self.assertFalse(res.success)
        self.assertTrue(res.rolled_back)
        # pehli (already-written) file rollback ho ke delete ho gayi
        self.assertFalse(os.path.exists(self._path("first_ok.py")))

    def test_path_traversal_blocked(self):
        payload = '''```json
{"edits": [{"path": "../evil.py", "action": "create", "content": "pwned"}]}
```'''
        coder = _coder_returning(payload)
        ed = MultiFileEditor(coder_agent=coder, root_dir=self.root)
        res = ed.edit("escape attempt", apply=True)
        self.assertFalse(res.success)
        self.assertTrue(any("traversal" in e for e in res.errors))
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.root), "evil.py")))

    def test_invalid_json_reported_gracefully(self):
        coder = _coder_returning("```json\n{not valid}\n```")
        ed = MultiFileEditor(coder_agent=coder, root_dir=self.root)
        res = ed.edit("broken json")
        self.assertFalse(res.success)
        self.assertTrue(any("invalid JSON" in e for e in res.errors))

    def test_python_syntax_error_blocks_plan(self):
        payload = '''```json
{"edits": [{"path": "bad.py", "action": "create", "content": "def broken(:\\n"}]}
```'''
        coder = _coder_returning(payload)
        ed = MultiFileEditor(coder_agent=coder, root_dir=self.root)
        res = ed.edit("bad python", apply=True)
        self.assertFalse(res.success)
        self.assertTrue(any("SyntaxError" in e for e in res.errors))
        self.assertFalse(os.path.exists(self._path("bad.py")))

    def test_patch_action_with_search_replace(self):
        os.makedirs(self._path("src"), exist_ok=True)
        with open(self._path("src/core.py"), "w", encoding="utf-8") as f:
            f.write("def run():\n    # old logic\n    return 10\n")
        payload = '''```json
{"edits": [{
  "path": "src/core.py",
  "action": "patch",
  "search": "    # old logic\\n    return 10",
  "replace": "    # new logic\\n    return 42"
}]}
```'''
        coder = _coder_returning(payload)
        ed = MultiFileEditor(coder_agent=coder, root_dir=self.root)
        res = ed.edit("update logic", apply=True)
        self.assertTrue(res.success, res.errors)
        with open(self._path("src/core.py"), encoding="utf-8") as f:
            content = f.read()
            self.assertIn("return 42", content)
            self.assertNotIn("return 10", content)

    def test_patch_action_with_aider_blocks(self):
        os.makedirs(self._path("src"), exist_ok=True)
        with open(self._path("src/utils.py"), "w", encoding="utf-8") as f:
            f.write("def helper():\n    return 'v1'\n")
        payload = '''```json
{"edits": [{
  "path": "src/utils.py",
  "action": "edit",
  "content": "<<<<<<< SEARCH\\ndef helper():\\n    return 'v1'\\n=======\\ndef helper():\\n    return 'v2'\\n>>>>>>>"
}]}
```'''
        coder = _coder_returning(payload)
        ed = MultiFileEditor(coder_agent=coder, root_dir=self.root)
        res = ed.edit("bump helper", apply=True)
        self.assertTrue(res.success, res.errors)
        with open(self._path("src/utils.py"), encoding="utf-8") as f:
            content = f.read()
            self.assertIn("return 'v2'", content)


class DetectLanguageTests(unittest.TestCase):
    def test_detection_table(self):
        cases = {
            "Write a TypeScript parser module": "typescript",
            "Create a react component in tsx": "typescript",
            "Build a Node.js HTTP server": "javascript",
            "Implement a golang worker pool": "go",
            "Write a rust CLI tool": "rust",
            "Spring boot java service": "java",
            "bash script to backup files": "bash",
            "Two-sum solution with tests": "python",
        }
        for task, expected in cases.items():
            self.assertEqual(CoderAgent.detect_language(task), expected, task)

    def test_prompt_injects_language_rules(self):
        coder = CoderAgent(model="fixed-model")
        captured = {}

        def fake_think(prompt, previous_error_reflexion=None, complexity_score=0.0):
            captured["prompt"] = prompt
            return MagicMock(success=True, content="```typescript\ncode\n```",
                             error_message="", model_used="m")

        with patch.object(coder, "think", side_effect=fake_think):
            coder.generate_code("make a typescript queue class")

        self.assertIn("TypeScript", captured["prompt"])
        self.assertIn("No `any` types", captured["prompt"])

    def test_tester_skips_ast_for_non_python(self):
        from saleha.agents.tester import TesterAgent
        tester = TesterAgent()
        valid_js = "function add(a, b) { return a + b; }"
        res = tester.test_code(valid_js, language="javascript")
        self.assertTrue(res.passed, res.error_message)  # JS ko Python AST se flag nahi karta


if __name__ == "__main__":
    unittest.main()
