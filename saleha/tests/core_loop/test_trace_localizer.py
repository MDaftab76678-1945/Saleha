"""Stack-trace localization: the repo source lines a failing run names, in any language."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from saleha.core.loop.trace_localizer import suspects_from_output


class TraceLocalizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name
        for rel in ("src/math.js", "src/math.test.js", "src/util.ts", "pkg/calc.go", "pkg/calc_test.go",
                    "src/lib.rs", "shop/pricing.py", "tests/test_pricing.py"):
            p = Path(self.root, rel)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("".join(f"line {i}\n" for i in range(1, 40)), encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def where(self, output: str) -> list:
        return [(s.file, s.line) for s in suspects_from_output(self.root, output)]

    def test_jest_frames_skip_the_test_file_and_node_modules(self) -> None:
        out = ("● math › adds\n\n    expect(received).toBe(expected)\n"
               f"      at add ({os.path.join(self.root, 'src', 'math.js')}:3:10)\n"
               f"      at Object.<anonymous> ({os.path.join(self.root, 'src', 'math.test.js')}:5:10)\n"
               f"      at Runtime ({os.path.join(self.root, 'node_modules', 'jest', 'x.js')}:9:1)\n")
        self.assertEqual(self.where(out), [("src/math.js", 3)])

    def test_vitest_and_file_urls(self) -> None:
        url = "file:///" + os.path.join(self.root, "src", "util.ts").replace("\\", "/").lstrip("/")
        out = f" ❯ src/util.ts:7:12\n    at {url}:8:3\n"
        self.assertEqual(self.where(out), [("src/util.ts", 7), ("src/util.ts", 8)])

    def test_go_and_rust(self) -> None:
        go = ("--- FAIL: TestAdd (0.00s)\n    calc_test.go:9: got 1 want 3\n"
              f"\t{os.path.join(self.root, 'pkg', 'calc.go')}:4 +0x1d\n")
        self.assertEqual(self.where(go), [("pkg/calc.go", 4)])
        rust = "thread 'tests::adds' panicked at src/lib.rs:12:5:\nassertion `left == right` failed\n"
        self.assertEqual(self.where(rust), [("src/lib.rs", 12)])

    def test_python_traceback_nearest_frame_first(self) -> None:
        out = (f'  File "{os.path.join(self.root, "tests", "test_pricing.py")}", line 9, in test_d\n'
               f'  File "{os.path.join(self.root, "shop", "pricing.py")}", line 4, in helper\n'
               f'  File "{os.path.join(self.root, "shop", "pricing.py")}", line 13, in discount\n')
        self.assertEqual(self.where(out), [("shop/pricing.py", 13), ("shop/pricing.py", 4)])

    def test_paths_outside_the_repo_are_ignored(self) -> None:
        self.assertEqual(self.where("    at f (/elsewhere/math.js:3:1)\n"), [])


if __name__ == "__main__":
    unittest.main()
