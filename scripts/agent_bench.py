"""Head-to-head coding benchmark for local agents (Saleha, Hermes, ...).

Each task is a folder with an empty solution.py and a test_solution.py built
from MBPP's own asserts. An agent gets the same prompt and the same model; the
score is computed here, afterwards, by running a pristine copy of the tests --
never from what the agent says. The agent's own "DONE"/"FAILED" claim is
recorded separately, so a false "done" is counted, not believed.

    # 1. build tasks (needs `datasets`: use .venv_train)
    .venv_train/Scripts/python scripts/agent_bench.py prepare --n 30
    # 2. run an agent
    .venv/Scripts/python scripts/agent_bench.py run saleha --model qwen3:8b
    .venv/Scripts/python scripts/agent_bench.py run hermes --model qwen3:8b
    # 3. compare
    .venv/Scripts/python scripts/agent_bench.py score

Agents edit files and run commands inside each task folder: this executes
model-written code on this machine.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench" / "agent_bench"
TASKS_DIR = BENCH / "tasks"
RUNS_DIR = BENCH / "runs"

PROMPT = (
    "You are working in the folder {folder}. solution.py is empty. Write Python code in "
    "solution.py so that `python -m pytest -q test_solution.py` passes. The task: {text} "
    "Do not edit test_solution.py. Run the tests yourself. Finish your final answer with the "
    "single word DONE if the tests pass, or FAILED if they do not."
)


def prepare(n: int) -> None:
    from datasets import load_dataset

    tasks = list(load_dataset("google-research-datasets/mbpp", "full")["test"])
    step = max(1, len(tasks) // n)
    chosen = tasks[::step][:n]
    if TASKS_DIR.exists():
        shutil.rmtree(TASKS_DIR)
    for t in chosen:
        d = TASKS_DIR / f"mbpp_{t['task_id']}"
        d.mkdir(parents=True)
        (d / "solution.py").write_text("", encoding="utf-8")
        setup = (t.get("test_setup_code") or "").strip()
        body = "\n".join(f"    {a}" for a in t["test_list"])
        (d / "test_solution.py").write_text(
            f"from solution import *  # noqa: F401,F403\n{setup}\n\n\ndef test_task() -> None:\n{body}\n",
            encoding="utf-8",
        )
        (d / "task.json").write_text(json.dumps({"task_id": t["task_id"], "text": t["text"]}),
                                     encoding="utf-8")
    print(f"prepared {len(chosen)} tasks in {TASKS_DIR}")


def verify(work: Path, pristine: Path) -> Dict[str, Any]:
    """Runs the ORIGINAL test file against the agent's solution.py."""
    shutil.copyfile(pristine / "test_solution.py", work / "test_solution.py")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_solution.py"],
            cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired:
        return {"passed": False, "detail": "tests timed out"}
    last = (proc.stdout.strip().splitlines() or [""])[-1]
    return {"passed": proc.returncode == 0, "detail": last[:200]}


def agent_command(agent: str, prompt: str, work: Path, model: str) -> List[str]:
    if agent == "saleha":
        exe = ROOT / ".venv" / "Scripts" / "saleha.exe"
        return [str(exe), "agent", prompt, "--dir", str(work), "--write", "-m", model,
                "--max-steps", "20", "--timeout", "600", "--json"]
    if agent in ("tourist", "tourist-claude", "tourist-gemini"):
        exe = ROOT / ".venv" / "Scripts" / "saleha.exe"
        return [str(exe), "tourist", prompt, "--dir", str(work), "--json"]
    if agent == "claude-code":
        # Claude Code as a full agent: it edits files and runs the tests
        # itself. Tools limited to reading, editing and running Python;
        # user/project settings are not loaded so the task is all it sees.
        exe = shutil.which("claude") or "claude"
        return [exe, "-p", prompt, "--output-format", "json", "--model", model,
                "--permission-mode", "acceptEdits",
                "--allowedTools", "Read Edit Write Glob Grep Bash(python *) Bash(pytest *)",
                "--setting-sources", "", "--no-session-persistence", "--strict-mcp-config"]
    if agent == "hermes":
        exe = shutil.which("hermes") or "hermes"
        return [exe, "-z", prompt, "--yolo", "--in", str(work), "-m", model]
    raise SystemExit(f"unknown agent {agent!r}")


def final_answer(agent: str, output: str) -> str:
    """Only the agent's own final answer -- never the echoed prompt.

    The prompt itself contains "DONE ... or FAILED", so searching the whole
    transcript counted a run that stopped with no answer as "FAILED".
    """
    if agent in ("saleha", "tourist", "tourist-claude", "tourist-gemini"):
        for line in reversed(output.splitlines()):
            line = line.strip()
            if line.startswith("{") and '"success"' in line:
                try:
                    return str(json.loads(line).get("final_message") or "")
                except ValueError:
                    continue
        return ""
    if agent == "claude-code":
        for line in reversed(output.splitlines()):
            line = line.strip()
            if line.startswith("{") and '"result"' in line:
                try:
                    return str(json.loads(line).get("result") or "")
                except ValueError:
                    continue
        return ""
    return output  # hermes -z prints only the final response


def claimed(answer: str) -> str:
    """The agent's own verdict: the last DONE/FAILED word in its final answer."""
    words = re.findall(r"\b(DONE|FAILED)\b", answer)
    return words[-1] if words else "none"


def run(agent: str, model: str, limit: int) -> None:
    tasks = sorted(p for p in TASKS_DIR.iterdir() if p.is_dir())
    if limit:
        tasks = tasks[:limit]
    if not tasks:
        raise SystemExit("no tasks: run `prepare` first")
    out_dir = RUNS_DIR / agent
    out_dir.mkdir(parents=True, exist_ok=True)
    # Claude Code walks up from its working directory loading CLAUDE.md and
    # rules; inside this repo it would read Saleha's own instructions. Its
    # task folders live outside the repo instead.
    work_root = (Path(tempfile.gettempdir()) / "saleha_agent_bench" / agent
                 if agent == "claude-code" else out_dir)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "SALEHA_APPROVAL": "off"}
    if agent == "tourist-claude":
        # Same harness as "tourist", but every model call goes to Claude --
        # isolates what the harness adds from what the model knows.
        env.update(SALEHA_TOURIST_FAST=f"claude-code:{model}", SALEHA_TOURIST_DEEP=f"claude-code:{model}")
    if agent == "tourist-gemini":
        env.update(SALEHA_TOURIST_FAST=f"gemini:{model}", SALEHA_TOURIST_DEEP=f"gemini:{model}")
    results: List[Dict[str, Any]] = []
    for i, src in enumerate(tasks, 1):
        work = work_root / src.name
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(src, work)
        text = json.loads((src / "task.json").read_text(encoding="utf-8"))["text"]
        cmd = agent_command(agent, PROMPT.format(folder=work, text=text), work, model)
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=900, env=env)
            output, code = proc.stdout + "\n" + proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            output, code = f"{exc.stdout or ''}\nTIMEOUT", -1
        except FileNotFoundError as exc:
            raise SystemExit(f"{agent} is not installed: {exc}") from exc
        (work / "_agent_output.txt").write_text(str(output), encoding="utf-8")
        v = verify(work, src)
        row = {"task": src.name, "passed": v["passed"],
               "claimed": claimed(final_answer(agent, str(output))),
               "exit_code": code, "seconds": round(time.time() - t0, 1), "detail": v["detail"]}
        results.append(row)
        print(f"[{i}/{len(tasks)}] {src.name}: passed={row['passed']} claimed={row['claimed']} "
              f"({row['seconds']}s)", flush=True)
    (out_dir / "results.json").write_text(
        json.dumps({"agent": agent, "model": model, "results": results}, indent=1), encoding="utf-8")
    summarize(agent, results)


def summarize(agent: str, results: List[Dict[str, Any]]) -> None:
    n = len(results)
    passed = sum(r["passed"] for r in results)
    false_done = sum(r["claimed"] == "DONE" and not r["passed"] for r in results)
    silent = sum(r["claimed"] == "none" for r in results)
    mins = sum(r["seconds"] for r in results) / 60
    print(f"{agent}: solved {passed}/{n} | false DONE {false_done} | no verdict {silent} | "
          f"{mins:.0f} min")


def score() -> None:
    for f in sorted(RUNS_DIR.glob("*/results.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        summarize(f"{data['agent']} ({data['model']})", data["results"])


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--n", type=int, default=30)
    r = sub.add_parser("run")
    r.add_argument("agent", choices=["saleha", "tourist", "tourist-claude", "tourist-gemini", "claude-code", "hermes"])
    r.add_argument("--model", default="qwen3:8b")
    r.add_argument("--limit", type=int, default=0)
    sub.add_parser("score")
    args = ap.parse_args()
    if args.cmd == "prepare":
        prepare(args.n)
    elif args.cmd == "run":
        run(args.agent, args.model, args.limit)
    else:
        score()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
