"""Mutation pin: would the tests also accept a slightly wrong version of a change?"""

from __future__ import annotations

import importlib.util
import os
import py_compile
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from saleha.core.verification import mutation_pin as mp

PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]


def _git(root: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=60, check=True)


class MutantGenerationTests(unittest.TestCase):
    def test_only_the_given_lines_are_mutated(self) -> None:
        src = b"def f(a, b):\n    x = a + b\n    return x * 2 > 3\n"
        got = mp.mutants_for(src, {3})
        self.assertTrue(got)
        self.assertTrue(all(line == 3 for line, _k, _new in got))
        kinds = {k for _l, k, _n in got}
        self.assertIn("'*' -> '/'", kinds)
        self.assertIn("'>' -> '>='", kinds)
        self.assertIn("2 -> 3", kinds)

    def test_booleans_and_not(self) -> None:
        got = {new for _l, _k, new in mp.mutants_for(b"def f(x):\n    return not x or True\n", {2})}
        self.assertIn(b"    return x or True", got)
        self.assertIn(b"    return not x or False", got)
        self.assertIn(b"    return not x and True", got)


class PinTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name
        Path(self.root, "price.py").write_bytes(b"def discount(total, percent):\n    return total\n")
        Path(self.root, "test_price.py").write_bytes(
            b"from price import discount\n\n\ndef test_ten():\n    assert discount(200, 10) == 180\n")
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"],
                     ["config", "core.autocrlf", "false"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
            _git(self.root, *args)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _fix(self, body: bytes) -> None:
        Path(self.root, "price.py").write_bytes(b"def discount(total, percent):\n" + body)

    def test_integer_inputs_leave_floor_division_unpinned(self) -> None:
        """Found by this check on its first run: with discount(200, 10) the tests cannot
        tell `/ 100` from `// 100` -- both give 180 -- so the fix is proven but LOOSE."""
        self._fix(b"    return total - total * percent / 100\n")
        before = Path(self.root, "price.py").read_bytes()
        rep = mp.pin(self.root, PYTEST)
        self.assertEqual(rep.verdict, mp.LOOSE, rep.reason)
        self.assertEqual([m.kind for m in rep.survivors], ["'/' -> '//'"])
        self.assertEqual(Path(self.root, "price.py").read_bytes(), before)    # restored byte for byte

    def test_a_test_that_tells_them_apart_pins_the_fix(self) -> None:
        Path(self.root, "test_price.py").write_bytes(
            b"import pytest\nfrom price import discount\n\n\ndef test_ten():\n"
            b"    assert discount(199, 10) == pytest.approx(179.1)\n")
        _git(self.root, "commit", "-q", "-am", "stronger test")
        self._fix(b"    return total - total * percent / 100\n")
        rep = mp.pin(self.root, PYTEST)
        self.assertEqual(rep.verdict, mp.PINNED, rep.reason)
        self.assertGreater(len(rep.mutants), 3)

    def test_a_cached_pyc_of_the_fix_is_not_what_the_mutants_run(self) -> None:
        """CI went red on this: a .pyc compiled in the same second as a same-size mutant
        is trusted, so the unmutated fix ran and '-' -> '+' "survived" test_ten. An
        unchecked-hash .pyc is trusted every time, which makes the case deterministic."""
        self._fix(b"    return total - total * percent / 100\n")
        src = os.path.join(self.root, "price.py")
        py_compile.compile(src, cfile=importlib.util.cache_from_source(src),
                           invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
        rep = mp.pin(self.root, PYTEST)
        self.assertEqual([m.kind for m in rep.survivors], ["'/' -> '//'"], rep.reason)

    def test_nothing_mutable_is_not_checked(self) -> None:
        self._fix(b"    return total  # comment only\n")
        self.assertEqual(mp.pin(self.root, PYTEST).verdict, mp.NOT_CHECKED)


if __name__ == "__main__":
    unittest.main()
