"""
Run a command under a timeout that holds for everything the command starts.

subprocess.run(timeout=...) kills only the direct child. A test command is
usually a launcher -- npm -> node, `go run` -> the built program -- so the
process doing the work outlives the kill. Measured on Windows: `npm test` on
a test that never ends, run with timeout=5, had not returned after 60s (run()
waits for the output pipes the orphaned node still holds) and left three node
processes running; an endless Go program under PolyglotExecutor(timeout=20)
had not returned after 75s. On POSIX run() does return, but the orphans keep
running.

run_bounded starts the command in its own session on POSIX and, on a timeout
or any interruption, kills the whole tree (taskkill /T on Windows, the
process group on POSIX) before collecting what was printed.
"""

from __future__ import annotations

import os
import signal
import subprocess
from typing import Any, Dict, List, Optional


def kill_tree(proc: "subprocess.Popen[Any]") -> None:
    """Kill `proc` and every process it started. Never raises."""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        proc.kill()
    except OSError:
        pass


def run_bounded(argv: List[str], cwd: Optional[str] = None, timeout: Optional[float] = None,
                env: Optional[Dict[str, str]] = None,
                input: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
    """subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
    errors="replace", ...) whose timeout kills the whole process tree.

    Raises subprocess.TimeoutExpired after the kill, as run() does, with the
    output printed so far on the exception.
    """
    extra: Dict[str, Any] = {} if os.name == "nt" else {"start_new_session": True}
    proc = subprocess.Popen(argv, cwd=cwd, env=env,
                            stdin=subprocess.PIPE if input is not None else None,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", **extra)
    try:
        out, err = proc.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        kill_tree(proc)
        try:
            exc.stdout, exc.stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pass        # a process outside the tree still holds the pipes: its output is lost
        raise
    except BaseException:
        kill_tree(proc)
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)
