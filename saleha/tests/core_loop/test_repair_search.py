"""repair_search: small edits at the suspect lines, chosen by running the tests -- no model."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import List

from saleha.core.loop import repair_search
from saleha.core.loop.fault_localizer import Suspect

PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]


def _s(file: str, line: int, score: float = 1.0) -> Suspect:
    return Suspect(file, line, score, "", "", (line, line))


def _afters(root: str, rel: str, line: int) -> List[str]:
    return [c.after for c, _data in repair_search.plan(root, [_s(rel, line)])]


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _file(self, text: str) -> str:
        Path(self.root, "m.py").write_bytes(text.encode())
        return "m.py"

    def test_the_commonest_one_token_fixes_come_first(self) -> None:
        rel = self._file("def f(a, b):\n    return a - b if a < b else 0\n")
        afters = _afters(self.root, rel, 2)
        # left to right on the line: the operator of `a - b`, then the comparison, boundary first
        self.assertEqual(afters[:3], ["return a + b if a < b else 0", "return a - b if a <= b else 0",
                                      "return a - b if a >= b else 0"])
        self.assertIn("return a + b if a < b else 0", afters)
        self.assertIn("return a - b if a < b else 1", afters)
        self.assertIn("return b - a if a < b else 0", afters, "operands of '-' swapped")

    def test_off_by_one_twins_none_checks_and_other_names_are_listed(self) -> None:
        rel = self._file("def f(xs, i, n):\n"
                         "    total = max(xs[i], len(xs))\n"
                         "    if n:\n"
                         "        return list(range(n))\n"
                         "    return total\n")
        self.assertTrue({"total = max(xs[i + 1], len(xs))", "total = max(xs[i - 1], len(xs))",
                         "total = max(xs[i], len(xs) - 1)", "total = min(xs[i], len(xs))",
                         "total = max(len(xs), xs[i])", "total = max(xs[n], len(xs))"}
                        <= set(_afters(self.root, rel, 2)))
        self.assertTrue({"if not n:", "if n is not None:"} <= set(_afters(self.root, rel, 3)))
        self.assertIn("return list(range(n + 1))", _afters(self.root, rel, 4))

    def test_an_off_by_one_adjustment_is_dropped_not_zeroed(self) -> None:
        rel = self._file("def page(items, start, size):\n    return items[start:start + size - 1]\n")
        afters = _afters(self.root, rel, 2)
        self.assertIn("return items[start:start + size]", afters)
        self.assertNotIn("return items[start:start + size - 0]", afters)
        self.assertIn("return items[start:start + size - 2]", afters)

    def test_every_listed_edit_parses_and_changes_one_line_only(self) -> None:
        src = "def f(a):\n    return (a+1) * 2 if not a else -a\n\nX = 3\n"
        rel = self._file(src)
        for c, data in repair_search.plan(self.root, [_s(rel, 2)]):
            compile(data, "m.py", "exec")
            changed = [i for i, (x, y) in enumerate(zip(src.split("\n"), data.decode().split("\n"))) if x != y]
            self.assertEqual(changed, [1], c)

    def test_a_file_with_a_bom_keeps_it_and_its_first_line_is_edited_right(self) -> None:
        Path(self.root, "m.py").write_bytes(b"\xef\xbb\xbfLIMIT = 4\r\nNAME = 'x'\r\n")
        plan = repair_search.plan(self.root, [_s("m.py", 1)])
        first = dict((c.after, data) for c, data in plan)["LIMIT = 5"]
        self.assertEqual(first, b"\xef\xbb\xbfLIMIT = 5\r\nNAME = 'x'\r\n")

    def test_files_it_cannot_change_give_an_empty_plan(self) -> None:
        Path(self.root, "app.js").write_text("const a = 1 - 2;\n", encoding="utf-8")
        Path(self.root, "bad.py").write_text("def (:\n", encoding="utf-8")
        self.assertEqual(repair_search.plan(self.root, [_s("app.js", 1), _s("bad.py", 1), _s("gone.py", 3)]), [])


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, name: str, text: str) -> None:
        Path(self.root, name).write_bytes(text.encode())

    def test_the_first_edit_the_tests_accept_stays_in_the_file(self) -> None:
        self._write("calc.py", "def add(a, b):\n    return a - b\n")
        self._write("test_calc.py", "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n")
        res = repair_search.search(self.root, [_s("calc.py", 2)], PYTEST)
        assert res.found is not None, res.reason
        self.assertEqual((res.found.kind, res.tried), ("'-' -> '+'", 1))
        self.assertEqual(Path(self.root, "calc.py").read_text(encoding="utf-8"), "def add(a, b):\n    return a + b\n")
        self.assertIn("no model", res.reason)

    def test_an_edit_that_breaks_other_tests_is_rejected_and_the_search_goes_on(self) -> None:
        self._write("grade.py", 'def grade(score):\n    return "pass" if score > 51 else "fail"\n')
        self._write("test_a.py", 'from grade import grade\n\n\ndef test_51():\n    assert grade(51) == "pass"\n')
        self._write("test_b.py", 'from grade import grade\n\n\ndef test_edges():\n'
                                 '    assert grade(50.5) == "pass"\n    assert grade(50) == "fail"\n')
        res = repair_search.search(self.root, [_s("grade.py", 2)], PYTEST + ["test_a.py"], PYTEST)
        assert res.found is not None, res.reason
        self.assertEqual(res.found.after, 'return "pass" if score > 50 else "fail"')
        self.assertEqual([e["outcome"] for e in res.log], ["suite fail", "suite fail", "fail", "fail", "pass"])

    def test_an_edit_that_never_ends_is_cut_off_and_undone(self) -> None:
        src = "def count_to(n):\n    i = 0\n    while i < n:\n        i += 1\n    return i + 1\n"
        self._write("count.py", src)
        self._write("test_count.py", "from count import count_to\n\n\ndef test_three():\n"
                                     "    assert count_to(3) == 3\n")
        res = repair_search.search(self.root, [_s("count.py", 4), _s("count.py", 5)], PYTEST, run_timeout=4)
        assert res.found is not None, res.reason
        self.assertEqual(res.found.after, "return i")
        self.assertIn("timeout", [e["outcome"] for e in res.log])
        self.assertEqual(Path(self.root, "count.py").read_text(encoding="utf-8"),
                         src.replace("return i + 1", "return i"))

    def test_nothing_found_leaves_the_file_byte_for_byte(self) -> None:
        original = b"\xef\xbb\xbfdef discount(total, percent):\r\n    return total\r\n"
        Path(self.root, "price.py").write_bytes(original)
        self._write("test_price.py", "from price import discount\n\n\ndef test_ten():\n"
                                     "    assert discount(200, 10) == 180\n")
        res = repair_search.search(self.root, [_s("price.py", 2)], PYTEST)
        self.assertIsNone(res.found)
        self.assertGreaterEqual(res.tried, 1)
        self.assertTrue(res.complete)
        self.assertIn("none of the", res.reason)
        self.assertEqual(Path(self.root, "price.py").read_bytes(), original)

    def test_pythons_did_you_mean_is_tried_first_on_any_line_of_the_file(self) -> None:
        self._write("sets.py", "def issub(a, b):\n    x = 1\n    return b.issupserset(a)\n\n\n"
                               "def untested(a, b):\n    return a.issupserset(b)\n")
        self._write("test_sets.py", "from sets import issub\n\n\ndef test_sub():\n    assert issub({1}, {1, 2})\n")
        out = "E   AttributeError: 'set' object has no attribute 'issupserset'. Did you mean: 'issuperset'?"
        res = repair_search.search(self.root, [_s("sets.py", 2)], PYTEST, output=out)
        assert res.found is not None, res.reason
        self.assertEqual((res.found.line, res.found.after, res.tried), (3, "return b.issuperset(a)", 1))
        self.assertIn("Python's suggestion, 2 lines", res.found.kind)
        self.assertNotIn("issupserset", Path(self.root, "sets.py").read_text(encoding="utf-8"), "every line fixed")

    def test_an_expected_exception_gets_a_guard_at_the_top_of_the_function(self) -> None:
        src = ('def sliced(seq, n):\n    """Slices of n."""\n    return [seq[i:i + n] for i in range(0, len(seq), n or 1)]\n')
        self._write("sl.py", src)
        self._write("test_sl.py", "import pytest\nfrom sl import sliced\n\n\ndef test_ok():\n"
                                  "    assert sliced('abcd', 2) == ['ab', 'cd']\n\n\ndef test_negative():\n"
                                  "    with pytest.raises(ValueError):\n        sliced('abcd', -1)\n")
        out = "E   Failed: DID NOT RAISE <class 'ValueError'>"
        self.assertEqual(repair_search.hints(out), ([], ["ValueError"]))
        res = repair_search.search(self.root, [_s("sl.py", 3)], PYTEST, output=out)
        assert res.found is not None, res.reason
        self.assertEqual(res.found.kind, "guard 'if n < 0: raise ValueError' added")
        self.assertIn("    if n < 0:\n        raise ValueError('n' + ' is invalid')\n    return",
                      Path(self.root, "sl.py").read_text(encoding="utf-8"))

    def test_a_spent_budget_says_so_instead_of_reading_as_a_clean_miss(self) -> None:
        self._write("calc.py", "def add(a, b):\n    return a - b\n")
        res = repair_search.search(self.root, [_s("calc.py", 2)], PYTEST, budget=0)
        self.assertEqual((res.found, res.tried, res.complete), (None, 0, False))
        self.assertIn("budget ran out", res.reason)

    def test_tests_that_cannot_start_stop_the_search(self) -> None:
        self._write("calc.py", "def add(a, b):\n    return a - b\n")
        res = repair_search.search(self.root, [_s("calc.py", 2)], [str(Path(self.root, "no-such-python"))])
        self.assertIsNone(res.found)
        self.assertIn("could not be started", res.reason)
        self.assertEqual(Path(self.root, "calc.py").read_text(encoding="utf-8"), "def add(a, b):\n    return a - b\n")


if __name__ == "__main__":
    unittest.main()
