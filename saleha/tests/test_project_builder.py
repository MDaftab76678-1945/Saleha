"""Unit tests for saleha.core.project_builder.ProjectBuilder.

ProjectBuilder itself had no test coverage before this file (found during a
test-coverage sweep of saleha/core/). These target the deterministic parsing
and file-isolation logic without a real model call -- the plan/generate
steps that do call a model are exercised only via the CLI-level mocked tests
in test_cli_debug.py, which stub out ProjectBuilder entirely.
"""

import unittest

from saleha.core.project_builder import (
    ProjectBuilder,
    FileSpec,
    FileResult,
)


class SlugifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ProjectBuilder()

    def test_slugify_lowercases_and_joins_with_underscores(self) -> None:
        self.assertEqual(
            self.builder._slugify("A Simple Command-Line Calculator"),
            "a_simple_command_line_calculator",
        )

    def test_slugify_truncates_to_forty_chars(self) -> None:
        long_goal = "build " + "x" * 100
        self.assertLessEqual(len(self.builder._slugify(long_goal)), 40)

    def test_slugify_falls_back_to_project_when_empty(self) -> None:
        self.assertEqual(self.builder._slugify("!!!"), "project")


class IsolateFileCodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ProjectBuilder()
        self.specs = [
            FileSpec(filename="app.py", description="entry point"),
            FileSpec(filename="calculator.py", description="math functions"),
        ]

    def test_single_file_project_returns_code_unchanged(self) -> None:
        code = "def add(a, b):\n    return a + b\n"
        result = self.builder._isolate_file_code(
            code, "solo.py", [FileSpec(filename="solo.py", description="only file")]
        )
        self.assertEqual(result, code)

    def test_no_marker_present_returns_whole_code(self) -> None:
        code = "def add(a, b):\n    return a + b\n"
        result = self.builder._isolate_file_code(code, "calculator.py", self.specs)
        self.assertEqual(result, code)

    def test_extracts_only_target_section_from_multi_file_dump(self) -> None:
        code = (
            "# app.py\n"
            "from calculator import add\n"
            "print(add(1, 2))\n"
            "# calculator.py\n"
            "def add(a, b):\n"
            "    return a + b\n"
        )
        result = self.builder._isolate_file_code(code, "calculator.py", self.specs)
        self.assertEqual(result, "def add(a, b):\n    return a + b")
        self.assertNotIn("from calculator import add", result)

    def test_single_mislabeled_section_is_still_used_whole(self) -> None:
        # The model wrote a header for the WRONG file, but the code is
        # clearly one complete file, not a genuine multi-file dump.
        code = "# app.py\ndef add(a, b):\n    return a + b\n"
        result = self.builder._isolate_file_code(code, "calculator.py", self.specs)
        self.assertEqual(result, "def add(a, b):\n    return a + b")


class FindEntryPointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ProjectBuilder()

    def test_finds_file_containing_dunder_main(self) -> None:
        specs = [
            FileSpec(filename="utils.py", description="helpers"),
            FileSpec(filename="app.py", description="entry point"),
        ]
        results = [
            FileResult(filename="utils.py", code="def helper(): pass", tested_ok=True),
            FileResult(filename="app.py", code="if __name__ == '__main__':\n    main()", tested_ok=True),
        ]
        entry = self.builder._find_entry_point(specs, results)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.filename, "app.py")

    def test_returns_none_when_no_file_has_dunder_main(self) -> None:
        specs = [FileSpec(filename="utils.py", description="helpers")]
        results = [FileResult(filename="utils.py", code="def helper(): pass", tested_ok=True)]
        self.assertIsNone(self.builder._find_entry_point(specs, results))


class IdentifyBuggyFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ProjectBuilder()
        self.specs = [
            FileSpec(filename="app.py", description="entry point"),
            FileSpec(filename="calculator.py", description="math functions"),
        ]

    def test_identifies_deepest_frame_matching_a_project_file(self) -> None:
        traceback_text = (
            'Traceback (most recent call last):\n'
            '  File "/tmp/proj/app.py", line 3, in <module>\n'
            '    main()\n'
            '  File "/tmp/proj/calculator.py", line 7, in add\n'
            '    return a + b\n'
            'TypeError: unsupported operand type\n'
        )
        buggy = self.builder._identify_buggy_file(traceback_text, self.specs)
        self.assertIsNotNone(buggy)
        self.assertEqual(buggy.filename, "calculator.py")

    def test_returns_none_when_traceback_has_no_frames(self) -> None:
        self.assertIsNone(self.builder._identify_buggy_file("no traceback here", self.specs))


class VerifyEntryPointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ProjectBuilder()

    def test_a_script_that_exits_zero_is_verified_ok(self) -> None:
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "ok.py"), "w", encoding="utf-8") as f:
                f.write("print('hello')\n")
            ok, error = self.builder._verify_entry_point(tmp, "ok.py")
            self.assertTrue(ok)
            self.assertEqual(error, "")

    def test_a_script_that_raises_is_reported_not_ok(self) -> None:
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "broken.py"), "w", encoding="utf-8") as f:
                f.write("raise RuntimeError('boom')\n")
            ok, error = self.builder._verify_entry_point(tmp, "broken.py")
            self.assertFalse(ok)
            self.assertIn("boom", error)


if __name__ == "__main__":
    unittest.main()
