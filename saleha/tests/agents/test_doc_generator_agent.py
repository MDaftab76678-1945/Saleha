"""Unit tests for saleha.agents.doc_generator.DocGeneratorAgent."""

import os
import tempfile
import unittest

from saleha.agents.doc_generator import DocGeneratorAgent


class DocGeneratorAgentTests(unittest.TestCase):

    def setUp(self) -> None:
        self.agent = DocGeneratorAgent()
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, rel_path: str, content: str) -> None:
        path = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_counts_reflect_the_real_scanned_directory(self) -> None:
        self._write("a.py", "class Foo:\n    pass\n\ndef bar():\n    pass\n")
        self._write("b.py", "class Baz:\n    pass\n\nclass Qux:\n    pass\n")
        spec = self.agent.scan_and_generate_docs(self.root)
        self.assertEqual(len(spec.modules_found), 2)
        self.assertEqual(spec.total_classes, 3)
        self.assertEqual(spec.total_functions, 1)

    def test_mermaid_diagram_reflects_real_agent_classes_not_a_fixed_list(self) -> None:
        # Regression guard: the diagram used to be a hardcoded string
        # claiming "19 First-Class Python Agents" and a fixed set of six
        # named agents, regardless of what was actually scanned. Two
        # different synthetic repos here must produce two different
        # diagrams.
        self._write("agents/one.py", "class OnlyAgentHere:\n    pass\n")
        spec_one = self.agent.scan_and_generate_docs(self.root)
        self.assertIn("OnlyAgentHere", spec_one.architecture_diagram_mermaid)
        self.assertNotIn("19 First-Class", spec_one.architecture_diagram_mermaid)
        self.assertNotIn("ArchitectAgent", spec_one.architecture_diagram_mermaid)

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as other_root:
            with open(os.path.join(other_root, "agents_module.py"), "w", encoding="utf-8") as f:
                pass  # no agents/ path component, no classes -- should not appear
            spec_two = self.agent.scan_and_generate_docs(other_root)
            self.assertNotIn("OnlyAgentHere", spec_two.architecture_diagram_mermaid)

    def test_no_agent_classes_found_is_stated_plainly(self) -> None:
        self._write("core/util.py", "def helper():\n    pass\n")
        spec = self.agent.scan_and_generate_docs(self.root)
        self.assertIn("No Agent Classes Found", spec.architecture_diagram_mermaid)

    def test_full_doc_markdown_has_no_decorative_emoji(self) -> None:
        self._write("x.py", "class X:\n    pass\n")
        spec = self.agent.scan_and_generate_docs(self.root)
        emoji_chars = "\U0001f3db\U0001f4ca\U0001f4d0\U0001f4da\U0001f4c4\u2728\U0001f4be"
        for ch in emoji_chars:
            self.assertNotIn(ch, spec.full_doc_markdown)

    def test_unparseable_file_is_skipped_not_fatal(self) -> None:
        self._write("broken.py", "def broken(:\n")
        self._write("ok.py", "class Ok:\n    pass\n")
        spec = self.agent.scan_and_generate_docs(self.root)
        # Both files are counted as "modules found" (the walk lists every
        # .py file before attempting to parse it), but only the parseable
        # one contributes to the class count.
        self.assertEqual(len(spec.modules_found), 2)
        self.assertEqual(spec.total_classes, 1)


if __name__ == "__main__":
    unittest.main()
