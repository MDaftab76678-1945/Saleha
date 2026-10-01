"""run_bounded: a timeout that holds for everything a command starts, not just the command."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from typing import Any, Callable, List

import psutil

from saleha.core.sandbox.bounded_run import run_bounded

# A launcher like npm or `go run`: it starts the process doing the work and
# waits on it. The worker inherits the output pipes and never ends.
LAUNCHER = ("import subprocess, sys\n"
            "worker = subprocess.Popen([sys.executable, '-c', 'import time\\nwhile True: time.sleep(0.1)'])\n"
            "open(sys.argv[1], 'w').write(str(worker.pid))\n"
            "worker.wait()\n")


def _gone(pid: int, within: float = 10.0) -> bool:
    end = time.monotonic() + within
    while time.monotonic() < end:
        try:
            if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                return True
        except psutil.NoSuchProcess:
            return True
        time.sleep(0.1)
    return False


class BoundedRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.pid_file = os.path.join(self._tmp.name, "worker.pid")
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._kill_worker)

    def _kill_worker(self) -> None:
        try:
            psutil.Process(self._worker_pid()).kill()
        except (psutil.Error, OSError, ValueError):
            pass

    def _worker_pid(self) -> int:
        with open(self.pid_file, encoding="utf-8") as fh:
            return int(fh.read())

    def _within(self, seconds: float, call: Callable[[], Any]) -> List[Any]:
        """[result] or [exception] of `call`; fails the test if it has not returned in time."""
        box: List[Any] = []

        def go() -> None:
            try:
                box.append(call())
            except BaseException as exc:      # the timeout is the expected outcome
                box.append(exc)

        t = threading.Thread(target=go, daemon=True)
        t.start()
        t.join(seconds)
        self.assertFalse(t.is_alive(), f"still running after {seconds}s: the timeout did not hold")
        return box

    def test_a_timeout_kills_the_launcher_and_what_it_started(self) -> None:
        argv = [sys.executable, "-c", LAUNCHER, self.pid_file]
        got = self._within(30, lambda: run_bounded(argv, timeout=3))
        self.assertIsInstance(got[0], subprocess.TimeoutExpired)
        self.assertTrue(_gone(self._worker_pid()), "the worker the launcher started is still running")

    def test_saleha_fix_test_runs_are_bounded_the_same_way(self) -> None:
        """The path `saleha fix` takes: measured on Windows, `npm test` on a test that never
        ends had not returned after 60s with timeout=5, and left node running."""
        from saleha.core.loop import fix_flow
        argv = [sys.executable, "-c", LAUNCHER, self.pid_file]
        got = self._within(30, lambda: fix_flow._run_tests(argv, self._tmp.name, 3))
        self.assertEqual(got[0], (None, "tests timed out after 3s"))
        self.assertTrue(_gone(self._worker_pid()), "the worker the launcher started is still running")

    def test_a_run_that_finishes_reads_like_subprocess_run(self) -> None:
        p = run_bounded([sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); "
                         "print(sys.stdin.read()); sys.exit(3)"], timeout=60, input="in")
        self.assertEqual((p.returncode, p.stdout.split(), p.stderr.strip()), (3, ["out", "in"], "err"))

    def test_output_is_decoded_as_utf8_whatever_the_console_code_page(self) -> None:
        """Compiler errors quote the source: CJK identifiers came back as mojibake under
        cp1252 when a call decoded with the platform default."""
        p = run_bounded([sys.executable, "-c", "import sys; sys.stderr.buffer.write('中文'.encode('utf-8'))"],
                        timeout=60)
        self.assertEqual(p.stderr, "中文")


if __name__ == "__main__":
    unittest.main()
