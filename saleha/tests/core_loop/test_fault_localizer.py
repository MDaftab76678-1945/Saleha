"""Fault localization: rank source lines by running each test under coverage."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from saleha.core.loop import fault_localizer as fl
from saleha.core.loop.agentic_loop import AgentLoop, _is_test_path

SRC = (
    "def area(w, h):\n"
    "    return w * h\n"
    "\n"
    "\n"
    "def discount(total, percent):\n"
    "    if percent < 0:\n"
    "        raise ValueError('negative')\n"
    "    return total - total * percent / 10\n"
)
TESTS = (
    "from shop import area, discount\n"
    "\n"
    "\n"
    "def test_area():\n"
    "    assert area(2, 3) == 6\n"
    "\n"
    "\n"
    "def test_discount():\n"
    "    assert discount(200, 10) == 180\n"
    "\n"
    "\n"
    "def test_negative():\n"
    "    import pytest\n"
    "    with pytest.raises(ValueError):\n"
    "        discount(1, -1)\n"
)


class OchiaiTests(unittest.TestCase):
    def test_a_line_only_failing_tests_run_outranks_a_shared_one(self) -> None:
        self.assertEqual(fl.ochiai(1, 0, 1), 1.0)
        self.assertLess(fl.ochiai(1, 3, 1), fl.ochiai(1, 0, 1))
        self.assertEqual(fl.ochiai(0, 5, 2), 0.0)

    def test_rank_orders_by_score_and_skips_test_files(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            Path(d, "shop.py").write_text(SRC, encoding="utf-8")
            src, tst = os.path.join(d, "shop.py"), os.path.join(d, "test_shop.py")
            lines = {"t::fail": {src: [6, 8], tst: [9]}, "t::pass": {src: [6]}}
            got = fl.rank(lines, {"t::fail": "failed", "t::pass": "passed"}, d, _is_test_path)
        self.assertEqual([(s.file, s.line) for s in got], [("shop.py", 8), ("shop.py", 6)])
        self.assertEqual(got[0].function, "discount")
        self.assertEqual(got[0].span, (5, 8))

    def test_rank_with_a_root_reached_through_a_symlink(self) -> None:
        """The tracer records real paths; a symlinked root must not push them all out as '..'."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            Path(d, "shop.py").write_text(SRC, encoding="utf-8")
            link = d + "_link"
            try:
                os.symlink(d, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("cannot create a symlink here")
            try:
                src = os.path.realpath(os.path.join(d, "shop.py"))
                got = fl.rank({"t::fail": {src: [8]}}, {"t::fail": "failed"}, link, _is_test_path)
            finally:
                os.unlink(link)
        self.assertEqual([(s.file, s.line) for s in got], [("shop.py", 8)])


class LocalizeTests(unittest.TestCase):
    def test_the_bug_line_ranks_first_in_a_real_pytest_run(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            Path(d, "shop.py").write_text(SRC, encoding="utf-8")
            Path(d, "test_shop.py").write_text(TESTS, encoding="utf-8")
            suspects, note = fl.localize(d, sys.executable, ["test_shop.py::test_discount"], timeout=120)
            self.assertTrue(suspects, note)
            self.assertEqual((suspects[0].file, suspects[0].line), ("shop.py", 8), note)
            self.assertIn("1 failing and 2 passing", note)
            text = fl.describe(suspects, note, d)
            self.assertIn("8:     return total - total * percent / 10    <-- most suspicious", text)
            self.assertIn("UNTRUSTED", text.upper())       # repo text framed as data
            self.assertEqual(sorted(os.listdir(d)), ["shop.py", "test_shop.py"])   # nothing written

    def test_no_failing_test_files_means_no_suspects_and_says_why(self) -> None:
        suspects, note = fl.localize(tempfile.gettempdir(), sys.executable, ["nope.py::t"])
        self.assertEqual(suspects, [])
        self.assertIn("no failing test files", note)


class FocusedReadTests(unittest.TestCase):
    """A whole-file read of a long file shows the localized region, not the head."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name
        body = "".join(f"def f{i}():\n    return {i}\n\n" for i in range(2000))
        Path(self.root, "big.py").write_text(body, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_read_without_a_range_shows_the_focus_region(self) -> None:
        loop = AgentLoop(agent=None, root_dir=self.root)
        loop.focus_ranges = {"big.py": (4501, 4503)}
        out = loop._tool_read_file("./big.py")
        self.assertIn("the region the failing tests point at", out)
        self.assertIn("4501: def f1500():", out)
        self.assertNotIn("def f0():", out)

    def test_without_focus_the_head_is_shown_as_before(self) -> None:
        out = AgentLoop(agent=None, root_dir=self.root)._tool_read_file("big.py")
        self.assertIn("def f0():", out)


if __name__ == "__main__":
    unittest.main()
