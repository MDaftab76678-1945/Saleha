"""
Saleha Agents: artifact checks -- what a model writes is checked by a program
before an agent calls it done.

Each check answers PASS, FAIL (with the reason) or NOT_RUN (with the reason
it could not run); "could not check" never reads as "passed". `produce()`
asks the model, runs the checks, and on a FAIL asks once more with the
failures quoted -- the model proposes, the checks decide.

Model-written Python is screened by the AST security auditor before it is
run, and runs in a throwaway directory with a timeout.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

PASS, FAIL, NOT_RUN = "PASS", "FAIL", "NOT_RUN"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


def verdict(checks: Sequence[Check]) -> Optional[bool]:
    """True: every check passed. False: one failed. None: nothing could be checked."""
    if any(c.status == FAIL for c in checks):
        return False
    if checks and all(c.status == PASS for c in checks):
        return True
    return None


def as_dicts(checks: Sequence[Check]) -> List[Dict[str, str]]:
    return [asdict(c) for c in checks]


_PROSE = ("markdown", "md", "text", "")


def fenced_blocks(text: str) -> List[Tuple[str, str]]:
    """(info, body) of every ``` block; info is the language word after the fence, lower case.

    Read line by line, because small models' fences are sloppy. Measured on
    qwen2.5-coder:3b: a ```markdown block left open with a ```python block
    inside it (a regex then finds no code at all), and content written on
    the fence line itself (```json {"palette": ...}).
    """
    blocks: List[Tuple[str, str]] = []
    info: Optional[str] = None
    body: List[str] = []
    for line in (text or "").splitlines():
        m = re.match(r"^\s*```\s*([^`]*?)\s*$", line)
        if not m:
            if info is not None:
                body.append(line)
            continue
        word, _, rest = m.group(1).partition(" ")
        word = word.lower()
        if info is not None:
            # A bare fence closes the block; a fence with a language closes it and
            # opens the next (nobody closes a block with ```css).
            blocks.append((info, "\n".join(body).strip("\n")))
            info, body = None, []
            if not word:
                continue
        info, body = word, ([rest.strip()] if rest.strip()[:1] in ("{", "[", "<", ":") else [])
    if info is not None and any(ln.strip() for ln in body):
        blocks.append((info, "\n".join(body).strip("\n")))          # never closed
    return blocks


def pick(blocks: Sequence[Tuple[str, str]], langs: Sequence[str] = (),
         contains: str = "", starts: str = "") -> str:
    """The first block whose info is one of `langs`, or whose body matches `contains`/`starts`."""
    for info, body in blocks:
        if info.split()[0:1] and info.split()[0] in langs:
            return body
    for _info, body in blocks:
        if (contains and re.search(contains, body)) or (starts and body.lstrip().lower().startswith(starts)):
            return body
    return ""


# -- Python -------------------------------------------------------------------

def check_python(code: str, name: str = "python syntax") -> Check:
    if not code.strip():
        return Check(name, FAIL, "no code")
    try:
        compile(code, "<model>", "exec")
    except SyntaxError as exc:
        return Check(name, FAIL, f"line {exc.lineno}: {exc.msg}")
    return Check(name, PASS)


def check_safe(code: str, name: str = "safe to run") -> Check:
    try:
        from saleha.sandbox.ast_security_verifier import ASTContractAuditor
    except ImportError as exc:
        return Check(name, NOT_RUN, f"security auditor unavailable: {exc}")
    ok, problems = ASTContractAuditor.audit(code, require_assertions=False)
    return Check(name, PASS) if ok else Check(name, FAIL, "; ".join(problems)[:300])


def run_python(code: str, timeout: float = 30.0, files: Optional[Dict[str, str]] = None,
               argv: Optional[List[str]] = None, name: str = "runs", screen: bool = True) -> Tuple[Check, str]:
    """Run model-written code in a throwaway directory. (check, output).

    `screen=False` only for a runner of our own whose model-written payload
    the caller has already passed through check_safe.
    """
    if screen:
        safe = check_safe(code + "\n" + "\n".join((files or {}).values()))
        if safe.status != PASS:
            return Check(name, NOT_RUN, f"not run: {safe.detail}"), ""
    with tempfile.TemporaryDirectory(prefix="saleha-artifact-", ignore_cleanup_errors=True) as tmp:
        for rel, body in {"main.py": code, **(files or {})}.items():
            with open(os.path.join(tmp, rel), "w", encoding="utf-8") as fh:
                fh.write(body)
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            p = subprocess.run(argv or [sys.executable, "main.py"], cwd=tmp, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            return Check(name, FAIL, f"timed out after {timeout:.0f}s"), ""
        except OSError as exc:
            return Check(name, NOT_RUN, f"could not start: {exc}"), ""
        out = (p.stdout + "\n" + p.stderr).strip()
        tail = " | ".join(out.splitlines()[-6:])[:400]
        return (Check(name, PASS, tail) if p.returncode == 0 else Check(name, FAIL, tail)), out


def run_tests(code: str, tests: str, timeout: float = 60.0) -> Check:
    """Run `tests` (pytest or unittest style) against `code` saved as solution.py."""
    if not tests.strip():
        return Check("tests pass", NOT_RUN, "no tests were written")
    if not re.search(r"\bdef test_?\w*", tests):
        return Check("tests pass", FAIL, "the test code has no test functions")
    if not re.search(r"\bassert|\.assert\w+\(|pytest\.raises", tests):
        return Check("tests pass", FAIL, "the tests assert nothing")
    if "solution" not in tests:
        tests = "from solution import *  # noqa\n" + tests
    safe = check_safe(code + "\n" + tests)
    if safe.status != PASS:
        return Check("tests pass", NOT_RUN, f"not run: {safe.detail}")
    # The runner is ours (it imports sys); only the model's code and tests are screened above.
    runner = ("import sys, unittest\n"
              "try:\n    import pytest\nexcept ImportError:\n    pytest = None\n"
              "if pytest is not None:\n"
              "    sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', 'test_solution.py']))\n"
              "suite = unittest.defaultTestLoader.discover('.', pattern='test_solution.py')\n"
              "sys.exit(0 if unittest.TextTestRunner().run(suite).wasSuccessful() else 1)\n")
    check, _out = run_python(runner, timeout=timeout, files={"solution.py": code, "test_solution.py": tests},
                             name="tests pass", screen=False)
    return check


# -- configuration files -----------------------------------------------------

def check_yaml(text: str, name: str, require: Optional[Callable[[Any], str]] = None) -> Check:
    """`require(data)` returns "" when the parsed document has what it needs, else the problem."""
    if not text.strip():
        return Check(name, FAIL, "missing")
    try:
        import yaml
    except ImportError as exc:
        return Check(name, NOT_RUN, f"PyYAML unavailable: {exc}")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return Check(name, FAIL, f"not valid YAML: {str(exc).splitlines()[0]}")
    problem = require(data) if require else ""
    return Check(name, FAIL, problem) if problem else Check(name, PASS)


def compose_problem(data: Any) -> str:
    if not isinstance(data, dict) or not isinstance(data.get("services"), dict) or not data["services"]:
        return "no services"
    bad = [k for k, v in data["services"].items() if not isinstance(v, dict) or not ({"image", "build"} & set(v))]
    return f"services without image or build: {', '.join(bad)}" if bad else ""


def workflow_problem(data: Any) -> str:
    if not isinstance(data, dict):
        return "not a mapping"
    if "on" not in data and True not in data:            # YAML 1.1 reads a bare `on:` key as True
        return "no `on:` trigger"
    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return "no jobs"
    for jname, job in jobs.items():
        if not isinstance(job, dict) or "runs-on" not in job or not job.get("steps"):
            return f"job {jname} needs runs-on and steps"
    return ""


_DOCKER = {"FROM", "RUN", "CMD", "LABEL", "EXPOSE", "ENV", "ADD", "COPY", "ENTRYPOINT", "VOLUME", "USER",
           "WORKDIR", "ARG", "ONBUILD", "STOPSIGNAL", "HEALTHCHECK", "SHELL", "MAINTAINER"}


def check_dockerfile(text: str) -> Check:
    name = "Dockerfile"
    lines, cont = [], False
    for raw in text.splitlines():
        line = raw.strip()
        if not cont and (not line or line.startswith("#")):
            continue
        if not cont:
            lines.append(line)
        cont = line.endswith("\\")
    if not lines:
        return Check(name, FAIL, "empty")
    words = [ln.split()[0].upper() for ln in lines]
    if words[0] not in ("FROM", "ARG"):
        return Check(name, FAIL, f"must start with FROM, starts with {words[0]}")
    unknown = sorted({w for w in words if w not in _DOCKER})
    if unknown:
        return Check(name, FAIL, f"unknown instructions: {', '.join(unknown)}")
    if "CMD" not in words and "ENTRYPOINT" not in words:
        return Check(name, FAIL, "no CMD or ENTRYPOINT")
    return Check(name, PASS)


def balanced(text: str, pairs: str = "{}") -> bool:
    depth = 0
    for ch in re.sub(r"(\"[^\"]*\"|'[^']*')", "", text):
        depth += (ch == pairs[0]) - (ch == pairs[1])
        if depth < 0:
            return False
    return depth == 0


def check_nginx(text: str) -> Check:
    name = "nginx config"
    if "server" not in text or not balanced(text):
        return Check(name, FAIL, "needs a server block with balanced braces")
    body = re.sub(r"#.*", "", text)
    for ln in body.splitlines():
        s = ln.strip()
        if s and not s.endswith(("{", "}", ";")):
            return Check(name, FAIL, f"directive without ';': {s[:60]}")
    return Check(name, PASS)


_SQL_START = ("CREATE", "ALTER", "INSERT", "SELECT", "DROP", "COMMENT", "WITH", "UPDATE", "DELETE",
              "GRANT", "SET", "BEGIN", "COMMIT", "DO")


def sql_statements(text: str) -> List[str]:
    body = re.sub(r"--[^\n]*", "", text)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    return [s.strip() for s in re.split(r";(?=(?:[^']*'[^']*')*[^']*$)", body) if s.strip()]


def check_sql(text: str) -> Check:
    """Structure only (statements, parentheses, at least one table): no database runs it here."""
    name = "SQL structure"
    stmts = sql_statements(text)
    if not stmts:
        return Check(name, FAIL, "no statements")
    for s in stmts:
        if not s.upper().startswith(_SQL_START):
            return Check(name, FAIL, f"not a SQL statement: {s[:60]}")
        if not balanced(s, "()"):
            return Check(name, FAIL, f"unbalanced parentheses in: {s[:60]}")
    if not any(re.match(r"(?i)CREATE\s+(?:UNLOGGED\s+)?TABLE", s) for s in stmts):
        return Check(name, FAIL, "no CREATE TABLE")
    return Check(name, PASS)


def sql_tables(text: str) -> List[str]:
    return re.findall(r"(?i)CREATE\s+(?:UNLOGGED\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?([\w.]+)", text)


def check_json(text: str, name: str = "JSON") -> Tuple[Check, Any]:
    """Valid JSON, read from the first { or [ (a model's trailing remark after it is left out, and said so)."""
    try:
        return Check(name, PASS), json.loads(text)
    except ValueError as exc:
        start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
        if start >= 0:
            try:
                data, end = json.JSONDecoder().raw_decode(text[start:])
                return Check(name, PASS, f"text around the JSON left out: {text[start + end:].strip()[:60]!r}"), data
            except ValueError:
                pass
        return Check(name, FAIL, f"not valid JSON: {exc}"), None


# -- web ----------------------------------------------------------------------

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: List[str] = []
        self.errors: List[str] = []
        self.seen: List[Tuple[str, Dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.seen.append((tag, {k: v or "" for k, v in attrs}))
        if tag not in _VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID:
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append(f"<{self.stack.pop()}> not closed")
            self.stack.pop()
        else:
            self.errors.append(f"</{tag}> without an opening tag")


def check_html(text: str) -> List[Check]:
    """Well-formed tags, plus the basics a page needs: lang, title, viewport, description, alt text."""
    p = _Tags()
    try:
        p.feed(text)
        p.close()
    except Exception as exc:                 # html.parser raises on some broken input
        return [Check("HTML well-formed", FAIL, str(exc))]
    errors = p.errors + [f"<{t}> not closed" for t in p.stack if t not in ("html", "body", "head", "p", "li")]
    out = [Check("HTML well-formed", FAIL, "; ".join(errors[:5])) if errors else Check("HTML well-formed", PASS)]
    tags = {t for t, _a in p.seen}
    attrs = [(t, a) for t, a in p.seen]
    missing = []
    if not any(t == "html" and a.get("lang") for t, a in attrs):
        missing.append("<html lang>")
    if "title" not in tags:
        missing.append("<title>")
    if not any(t == "meta" and a.get("name") == "viewport" for t, a in attrs):
        missing.append("viewport meta")
    if not any(t == "meta" and a.get("name") == "description" for t, a in attrs):
        missing.append("description meta")
    if any(t == "img" and "alt" not in a for t, a in attrs):
        missing.append("alt text on every <img>")
    out.append(Check("page basics", FAIL, "missing " + ", ".join(missing)) if missing else Check("page basics", PASS))
    return out


def check_css(text: str) -> Check:
    if not text.strip():
        return Check("CSS", FAIL, "empty")
    body = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    if not balanced(body):
        return Check("CSS", FAIL, "unbalanced braces")
    if not re.search(r"[^{}]+\{[^{}]*:[^{}]*\}", body):
        return Check("CSS", FAIL, "no rules")
    return Check("CSS", PASS)


def check_js(text: str) -> Check:
    import shutil
    if not text.strip():
        return Check("JavaScript syntax", FAIL, "empty")
    node = shutil.which("node")
    if not node:
        return Check("JavaScript syntax", NOT_RUN, "node is not installed")
    with tempfile.TemporaryDirectory(prefix="saleha-js-", ignore_cleanup_errors=True) as tmp:
        path = os.path.join(tmp, "app.js")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            p = subprocess.run([node, "--check", path], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return Check("JavaScript syntax", NOT_RUN, str(exc))
    if p.returncode == 0:
        return Check("JavaScript syntax", PASS)
    return Check("JavaScript syntax", FAIL, " | ".join(p.stderr.strip().splitlines()[:4])[:300])


_MERMAID = ("graph", "flowchart", "sequencediagram", "classdiagram", "statediagram", "erdiagram", "gantt",
            "pie", "journey", "mindmap", "timeline", "gitgraph")


def check_mermaid(text: str) -> Check:
    first = (text.strip().splitlines() or [""])[0].strip().lower()
    if not first.startswith(_MERMAID):
        return Check("Mermaid diagram", FAIL, f"unknown diagram type: {first[:30]}")
    if first.startswith(("graph", "flowchart")) and "--" not in text:
        return Check("Mermaid diagram", FAIL, "a graph with no edges")
    return Check("Mermaid diagram", PASS)


def _luminance(color: str) -> Optional[float]:
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", color.strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(fg: str, bg: str) -> Optional[float]:
    """WCAG 2 contrast ratio of two hex colours, None when either is not hex."""
    a, b = _luminance(fg), _luminance(bg)
    if a is None or b is None:
        return None
    hi, lo = max(a, b), min(a, b)
    return round((hi + 0.05) / (lo + 0.05), 2)


_PLACEHOLDER = re.compile(r"(?im)^\s*(?:#|//)\s*(?:TODO|FIXME)\b|NotImplementedError|your code here|"
                          r"<placeholder>|^\s*\.\.\.\s*$|^\s*pass\s*#\s*(?:todo|implement)")


def check_answer(content: str, no_placeholders: bool = True) -> List[Check]:
    """Checks for a free-form answer: every fenced block checked by its language.

    Used for the persona agents, whose answers can be anything: prose is
    left alone, but code, JSON, YAML, SQL, HTML, JavaScript and Dockerfiles
    in it must be valid, and code must not be a placeholder.
    """
    if not (content or "").strip():
        return [Check("answer has content", FAIL, "empty answer")]
    checks: List[Check] = []
    for i, (info, body) in enumerate(fenced_blocks(content), 1):
        lang = (info.split() or [""])[0]
        tag = f"block {i} ({lang or 'text'})"
        if lang in ("python", "py"):
            c = check_python(body, tag)
        elif lang == "json":
            c = check_json(body, tag)[0]
        elif lang in ("yaml", "yml"):
            c = check_yaml(body, tag)
        elif lang in ("javascript", "js"):
            c = check_js(body)
            c.name = tag
        elif lang in ("html",):
            c = check_html(body)[0]
            c.name = tag
        elif lang in ("dockerfile", "docker"):
            c = check_dockerfile(body)
            c.name = tag
        elif lang == "sql":
            bad = [s for s in sql_statements(body) if not s.upper().startswith(_SQL_START) or not balanced(s, "()")]
            c = Check(tag, FAIL if bad else PASS, f"not valid SQL: {bad[0][:60]}" if bad else "")
        else:
            continue
        checks.append(c)
        if no_placeholders and lang not in ("json", "yaml", "yml", "sql") and _PLACEHOLDER.search(body):
            checks.append(Check(f"{tag} complete", FAIL, "a placeholder is left in the code"))
    return checks or [Check("answer has content", PASS, "prose only, nothing to run")]


# -- the loop -----------------------------------------------------------------

MODEL_NOTES = ("model answered", "model answer used")


def artifact_verdict(checks: Sequence[Check]) -> Optional[bool]:
    """The verdict on the artifact returned, leaving out the notes about the model's answer."""
    return verdict([c for c in checks if c.name not in MODEL_NOTES])


def fallback_note(checks: Sequence[Check], answered: bool) -> List[Check]:
    """One line saying why the model's answer was replaced by the template."""
    if not answered:
        return [c for c in checks if c.name == "model answered"] or [Check("model answered", NOT_RUN, "no answer")]
    failed = "; ".join(f"{c.name}: {c.detail}" for c in checks if c.status == FAIL) or "nothing usable in it"
    return [Check("model answer used", FAIL, f"replaced by the template -- {failed}"[:400])]

def produce(agent: Any, prompt: str, build: Callable[[str], Tuple[Any, List[Check]]],
            repair_rounds: int = 1) -> Tuple[Any, List[Check], Any, int]:
    """(result, checks, last model response, repair rounds used).

    result is None and checks hold one NOT_RUN entry when no model answered.
    After a failed check the model is asked again with the failures quoted.
    """
    resp = agent.think(prompt)
    if not resp.success or not (resp.content or "").strip():
        return None, [Check("model answered", NOT_RUN, resp.error_message or "no answer")], resp, 0
    result, checks = build(resp.content)
    rounds = 0
    while verdict(checks) is False and rounds < repair_rounds:
        failed = "; ".join(f"{c.name}: {c.detail}" for c in checks if c.status == FAIL)
        again = agent.think(prompt + "\n\nYour previous answer failed these checks. Fix them and answer again "
                                     "in the same format:\n" + failed[:1500])
        rounds += 1
        if not again.success or not (again.content or "").strip():
            break
        result, checks = build(again.content)
        resp = again
    return result, checks, resp, rounds
