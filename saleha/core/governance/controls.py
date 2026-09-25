"""Security controls as code, with a ratchet.

Each control is a function that inspects the real repository (or executes the
real code path) and returns PASS / FAIL / NOT_CHECKED with the evidence it
used. Nothing here trusts a docstring or a doc: a control that cannot run
says NOT_CHECKED, never PASS.

Some controls measure a count (e.g. subprocess calls without a timeout). Those
are ratcheted against ``baseline.json``: the control FAILs if the count went
up since the baseline, and ``update_baseline`` only ever lowers a recorded
value. That is how the framework improves itself without being able to
quietly accept a regression -- raising a baseline takes a human edit that
shows up in review.
"""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"

PASS = "PASS"
FAIL = "FAIL"
NOT_CHECKED = "NOT_CHECKED"

_SKIP_DIRS = {".git", ".venv", ".venv_train", "node_modules", "__pycache__", "target",
              "build", "dist", ".pytest_cache", ".ruff_cache", ".mypy_cache"}


@dataclass
class ControlResult:
    control_id: str
    title: str
    status: str
    evidence: str
    metric: Optional[str] = None
    value: Optional[int] = None
    baseline: Optional[int] = None
    items: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Control:
    control_id: str
    title: str
    checks: str
    run: Callable[["ControlContext"], ControlResult]


@dataclass
class ControlContext:
    root: Path
    baseline: Dict[str, int]


# ---------------------------------------------------------------- helpers

def iter_python_files(root: Path, include_tests: bool = False) -> Iterator[Path]:
    """Python files of the saleha package under `root`."""
    pkg = root / "saleha"
    for dirpath, dirnames, filenames in os.walk(pkg):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        rel_parts = Path(dirpath).relative_to(root).parts
        if not include_tests and "tests" in rel_parts:
            continue
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath) / name


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


_SUBPROCESS_FUNCS = {"run", "call", "check_call", "check_output"}


def _subprocess_aliases(tree: ast.AST) -> Tuple[set, set]:
    """(names bound to the subprocess module, names bound to its run-like functions)."""
    modules, funcs = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "subprocess":
                    modules.add(a.asname or "subprocess")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for a in node.names:
                if a.name in _SUBPROCESS_FUNCS:
                    funcs.add(a.asname or a.name)
    return modules, funcs


def subprocess_calls(tree: ast.AST) -> Iterator[ast.Call]:
    """Every call to subprocess.run/call/check_call/check_output, through aliases too."""
    modules, funcs = _subprocess_aliases(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        via_module = (isinstance(f, ast.Attribute) and f.attr in _SUBPROCESS_FUNCS
                      and isinstance(f.value, ast.Name) and f.value.id in modules)
        via_name = isinstance(f, ast.Name) and f.id in funcs
        if via_module or via_name:
            yield node


def _kw(node: ast.Call, name: str) -> Optional[ast.keyword]:
    return next((k for k in node.keywords if k.arg == name), None)


def _has_kwargs_splat(node: ast.Call) -> bool:
    # subprocess.run(cmd, **opts): the options are not visible statically.
    return any(k.arg is None for k in node.keywords)


def _is_true(node: Optional[ast.keyword]) -> bool:
    return node is not None and isinstance(node.value, ast.Constant) and bool(node.value.value)


def find_subprocess_issues(root: Path, kind: str) -> Tuple[List[str], List[str]]:
    """(items, unparsed files) for kind 'timeout' or 'encoding'.

    'timeout':  run-like call with no timeout= (it can hang forever).
    'encoding': text-mode call (text=True / universal_newlines=True) with no
                encoding= (decodes as cp1252 on this machine).
    """
    items: List[str] = []
    unparsed: List[str] = []
    for path in iter_python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            unparsed.append(_rel(root, path))
            continue
        for call in subprocess_calls(tree):
            if _has_kwargs_splat(call):
                continue
            if kind == "timeout" and _kw(call, "timeout") is None:
                items.append(f"{_rel(root, path)}:{call.lineno}")
            elif kind == "encoding":
                text_mode = _is_true(_kw(call, "text")) or _is_true(_kw(call, "universal_newlines"))
                if text_mode and _kw(call, "encoding") is None:
                    items.append(f"{_rel(root, path)}:{call.lineno}")
    return items, unparsed


def _ratchet(ctx: ControlContext, control_id: str, title: str, metric: str,
             items: List[str], unparsed: List[str], what: str) -> ControlResult:
    value = len(items)
    baseline = ctx.baseline.get(metric)
    note = f"; {len(unparsed)} file(s) could not be parsed: {', '.join(unparsed[:5])}" if unparsed else ""
    if unparsed:
        # A partial scan must not read as a clean one.
        return ControlResult(control_id, title, NOT_CHECKED,
                             f"{value} {what} found, but the scan was incomplete{note}",
                             metric, value, baseline, items)
    if baseline is None:
        return ControlResult(control_id, title, NOT_CHECKED,
                             f"{value} {what}; no baseline recorded (run with --update-baseline)",
                             metric, value, None, items)
    if value > baseline:
        return ControlResult(control_id, title, FAIL,
                             f"{value} {what}, up from baseline {baseline}",
                             metric, value, baseline, items)
    trend = "unchanged" if value == baseline else f"improved from {baseline}"
    return ControlResult(control_id, title, PASS, f"{value} {what} ({trend})",
                         metric, value, baseline, items)


# ---------------------------------------------------------------- controls

def _catalog_control(ctx: ControlContext) -> ControlResult:
    cid, title = "GOV-SAST-CATALOG", "Scanner rules match their catalog"
    src_path = ctx.root / "saleha" / "core" / "verification" / "security_scanner.py"
    try:
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
        from saleha.core.verification.security_scanner import RULE_CATALOG
    except (OSError, SyntaxError, ImportError) as exc:
        return ControlResult(cid, title, NOT_CHECKED, f"could not load scanner: {exc}")

    emitted: Dict[str, set] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "SecurityVulnerability":
            kws = {k.arg: k.value for k in node.keywords}
            rid, sev = kws.get("rule_id"), kws.get("severity")
            if (isinstance(rid, ast.Constant) and isinstance(rid.value, str)
                    and isinstance(sev, ast.Constant) and isinstance(sev.value, str)):
                emitted.setdefault(rid.value, set()).add(sev.value)

    problems = []
    for rid, sevs in sorted(emitted.items()):
        info = RULE_CATALOG.get(rid)
        if info is None:
            problems.append(f"{rid} is emitted but not in RULE_CATALOG")
        elif sevs != {info.severity}:
            problems.append(f"{rid} emitted as {sorted(sevs)} but catalogued as {info.severity}")
    for rid in sorted(set(RULE_CATALOG) - set(emitted)):
        problems.append(f"{rid} is catalogued but never emitted")
    if not emitted:
        return ControlResult(cid, title, NOT_CHECKED, "found no findings with constant rule_id/severity")
    if problems:
        return ControlResult(cid, title, FAIL, f"{len(problems)} mismatch(es)", items=problems)
    return ControlResult(cid, title, PASS, f"{len(emitted)} rules, ids and severities agree")


def _rule_tests_control(ctx: ControlContext) -> ControlResult:
    cid, title = "GOV-SAST-TESTS", "Every scanner rule is exercised by a test"
    try:
        from saleha.core.verification.security_scanner import RULE_CATALOG
    except ImportError as exc:
        return ControlResult(cid, title, NOT_CHECKED, f"could not load scanner: {exc}")
    tests_dir = ctx.root / "saleha" / "tests"
    if not tests_dir.is_dir():
        return ControlResult(cid, title, NOT_CHECKED, "saleha/tests not found")
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in tests_dir.glob("test_*.py"))
    untested = [rid for rid in sorted(RULE_CATALOG) if not re.search(rf"\b{rid}\b", text)]
    return _ratchet(ctx, cid, title, "untested_scanner_rules", untested, [],
                    "rule(s) never named in a test")


def _local_only_control(_ctx: ControlContext) -> ControlResult:
    """Executes each cloud-capable provider with SALEHA_LOCAL_ONLY=1.

    Network and CLI calls are intercepted: an attempt is recorded, not made.
    """
    cid, title = "GOV-LOCAL-ONLY", "SALEHA_LOCAL_ONLY=1 blocks every cloud call"
    try:
        # Not `from saleha.core.platform import model_provider`: the package
        # rebinds that name to the provider singleton (see STRUCTURE.md).
        import importlib
        mp = importlib.import_module("saleha.core.platform.model_provider")
    except ImportError as exc:
        return ControlResult(cid, title, NOT_CHECKED, f"could not import model_provider: {exc}")

    attempts: List[str] = []

    def _record(label: str):
        def _fake(*args, **kwargs):
            attempts.append(label)
            raise RuntimeError("governance probe: outbound call intercepted")
        return _fake

    env = {"SALEHA_LOCAL_ONLY": "1", "OPENAI_API_KEY": "governance-probe",
           "GROQ_API_KEY": "governance-probe", "GEMINI_API_KEY": "governance-probe"}
    leaks: List[str] = []
    checked: List[str] = []
    with mock.patch.dict(os.environ, env), \
            mock.patch.object(mp.requests, "post", _record("requests.post")), \
            mock.patch.object(mp.requests, "get", _record("requests.get")), \
            mock.patch.object(mp.subprocess, "run", _record("subprocess.run")):
        probes = [
            ("OpenAICompatibleProvider(api.openai.com)",
             lambda: mp.OpenAICompatibleProvider(base_url="https://api.openai.com/v1")),
            ("ClaudeCodeProvider", lambda: mp.ClaudeCodeProvider(executable="claude-probe")),
            ("GeminiProvider", lambda: mp.GeminiProvider()),
        ]
        for name, make in probes:
            try:
                provider = make()
            except Exception as exc:  # a provider that cannot be built is not a leak, but say so
                leaks.append(f"{name}: could not construct ({exc})")
                continue
            before = len(attempts)
            available = provider.is_available()
            try:
                succeeded = provider.generate(model="probe", prompt="governance probe").success
            except Exception:
                succeeded = False  # the intercepted call raised; the attempt is what counts
            checked.append(name)
            if available:
                leaks.append(f"{name}: is_available() is True under local-only")
            if succeeded:
                leaks.append(f"{name}: generate() succeeded under local-only")
            if len(attempts) > before:
                leaks.append(f"{name}: attempted {attempts[before]} under local-only")
    if leaks:
        return ControlResult(cid, title, FAIL, f"{len(leaks)} leak(s)", items=leaks)
    return ControlResult(cid, title, PASS,
                         f"{len(checked)} cloud providers refused with no outbound attempt",
                         items=checked)


def _commit_gate_control(ctx: ControlContext) -> ControlResult:
    cid, title = "GOV-COMMIT-GATE", "The pre-commit gate is installed and runs preflight_lint"
    hook = ctx.root / ".git" / "hooks" / "pre-commit"
    gate = ctx.root / ".agents" / "scripts" / "preflight_lint.py"
    if not (ctx.root / ".git").is_dir():
        return ControlResult(cid, title, NOT_CHECKED, "not a git checkout (worktree or export)")
    if not gate.is_file():
        return ControlResult(cid, title, FAIL, "preflight_lint.py is missing")
    if not hook.is_file():
        return ControlResult(cid, title, FAIL, ".git/hooks/pre-commit is not installed")
    if "preflight_lint.py" not in hook.read_text(encoding="utf-8", errors="replace"):
        return ControlResult(cid, title, FAIL, "pre-commit hook does not run preflight_lint.py")
    return ControlResult(cid, title, PASS, "hook installed and calls preflight_lint.py")


def _timeout_control(ctx: ControlContext) -> ControlResult:
    items, unparsed = find_subprocess_issues(ctx.root, "timeout")
    return _ratchet(ctx, "GOV-SUBPROCESS-TIMEOUT", "subprocess calls have a timeout",
                    "subprocess_without_timeout", items, unparsed, "subprocess call(s) without timeout=")


def _encoding_control(ctx: ControlContext) -> ControlResult:
    items, unparsed = find_subprocess_issues(ctx.root, "encoding")
    return _ratchet(ctx, "GOV-SUBPROCESS-ENCODING", "text-mode subprocess calls set an encoding",
                    "subprocess_text_without_encoding", items, unparsed,
                    "text-mode subprocess call(s) without encoding=")


def _self_scan_control(ctx: ControlContext) -> ControlResult:
    cid, title = "GOV-SAST-SELF", "High-severity scanner findings in Saleha's own code"
    from saleha.core.verification.security_scanner import ASTSecurityScanner
    scanner = ASTSecurityScanner()
    items: List[str] = []
    unparsed: List[str] = []
    for path in iter_python_files(ctx.root):
        try:
            code = path.read_text(encoding="utf-8")
            ast.parse(code)
        except (SyntaxError, UnicodeDecodeError, OSError):
            unparsed.append(_rel(ctx.root, path))
            continue
        for v in scanner.scan_code(code, filename=path.name):
            if v.severity == "HIGH":
                items.append(f"{_rel(ctx.root, path)}:{v.line_number} {v.rule_id}")
    return _ratchet(ctx, cid, title, "high_sast_findings", items, unparsed, "HIGH finding(s)")


def _docs_rules_control(ctx: ControlContext) -> ControlResult:
    cid, title = "GOV-DOCS-RULES", "docs/SECURITY_MODEL.md rule table matches the catalog"
    from saleha.core.governance import doc_sync
    path = ctx.root / "docs" / "SECURITY_MODEL.md"
    if not path.is_file():
        return ControlResult(cid, title, FAIL, "docs/SECURITY_MODEL.md is missing")
    text = path.read_text(encoding="utf-8")
    current = doc_sync.extract_region(text, "security-rules")
    if current is None:
        return ControlResult(cid, title, FAIL, "no <!-- saleha:generated:security-rules --> region")
    if current.strip() != doc_sync.render_region("security-rules", ctx.root).strip():
        return ControlResult(cid, title, FAIL, "region is stale (run `saleha governance docs --apply`)")
    return ControlResult(cid, title, PASS, "rule table generated from RULE_CATALOG and current")


def _stale_docs_control(ctx: ControlContext) -> ControlResult:
    from saleha.core.governance import doc_sync
    claims = doc_sync.find_stale_claims(ctx.root)
    items = [f"{c.doc}:{c.line} {c.claim} ({c.reason})" for c in claims]
    return _ratchet(ctx, "GOV-DOCS-STALE", "Docs only reference commands and paths that exist",
                    "stale_doc_claims", items, [], "stale doc claim(s)")


def _version_control(ctx: ControlContext) -> ControlResult:
    cid, title = "GOV-VERSION", "Every version declaration agrees"
    from saleha.core.governance import versioning
    found = versioning.version_declarations(ctx.root)
    if not found:
        return ControlResult(cid, title, NOT_CHECKED, "no version declarations found")
    values = {v for v in found.values() if v}
    items = [f"{k}: {v or 'missing'}" for k, v in found.items()]
    if len(values) != 1 or not all(found.values()):
        return ControlResult(cid, title, FAIL, "version declarations disagree", items=items)
    return ControlResult(cid, title, PASS, f"all {len(found)} declare {values.pop()}", items=items)


CONTROLS: List[Control] = [
    Control("GOV-SAST-CATALOG", "Scanner rules match their catalog",
            "Parses security_scanner.py; every emitted rule_id/severity must equal RULE_CATALOG.",
            _catalog_control),
    Control("GOV-SAST-TESTS", "Every scanner rule is exercised by a test",
            "Each RULE_CATALOG id must be named in a saleha/tests file (ratchet).", _rule_tests_control),
    Control("GOV-DOCS-RULES", "docs/SECURITY_MODEL.md rule table matches the catalog",
            "The generated rule table must equal a fresh render of RULE_CATALOG.", _docs_rules_control),
    Control("GOV-LOCAL-ONLY", "SALEHA_LOCAL_ONLY=1 blocks every cloud call",
            "Runs each cloud provider with local-only set and intercepts network/CLI calls.",
            _local_only_control),
    Control("GOV-COMMIT-GATE", "The pre-commit gate is installed and runs preflight_lint",
            "Checks .git/hooks/pre-commit exists and invokes preflight_lint.py.", _commit_gate_control),
    Control("GOV-SUBPROCESS-TIMEOUT", "subprocess calls have a timeout",
            "Counts run/call/check_call/check_output without timeout= (ratchet).", _timeout_control),
    Control("GOV-SUBPROCESS-ENCODING", "text-mode subprocess calls set an encoding",
            "Counts text=True calls without encoding= (ratchet).", _encoding_control),
    Control("GOV-SAST-SELF", "High-severity scanner findings in Saleha's own code",
            "Runs the SAST scanner over saleha/ excluding tests (ratchet).", _self_scan_control),
    Control("GOV-DOCS-STALE", "Docs only reference commands and paths that exist",
            "Checks backticked `saleha ...` commands and repo paths in docs (ratchet).",
            _stale_docs_control),
    Control("GOV-VERSION", "Every version declaration agrees",
            "pyproject.toml and saleha/__init__.py must declare the same version.", _version_control),
]


# ---------------------------------------------------------------- running

def load_baseline(path: Path = BASELINE_PATH) -> Dict[str, int]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: int(v) for k, v in data.get("metrics", {}).items()}


def run_controls(root: Optional[Path] = None, baseline: Optional[Dict[str, int]] = None,
                 only: Optional[List[str]] = None) -> List[ControlResult]:
    ctx = ControlContext(root=Path(root or REPO_ROOT), baseline=
                         load_baseline() if baseline is None else baseline)
    results = []
    for control in CONTROLS:
        if only and control.control_id not in only:
            continue
        try:
            results.append(control.run(ctx))
        except Exception as exc:  # a crashed control proved nothing
            results.append(ControlResult(control.control_id, control.title, NOT_CHECKED,
                                         f"control crashed: {type(exc).__name__}: {exc}"))
    return results


def update_baseline(results: List[ControlResult], path: Path = BASELINE_PATH) -> Dict[str, Tuple[Optional[int], int]]:
    """Record measured metrics. Only lowers existing values or adds missing ones.

    Returns {metric: (old, new)} for what changed. A metric measured by a
    control that was NOT_CHECKED because its scan was incomplete is skipped.
    """
    current = load_baseline(path)
    changed: Dict[str, Tuple[Optional[int], int]] = {}
    for r in results:
        if r.metric is None or r.value is None:
            continue
        if r.status == NOT_CHECKED and r.baseline is not None:
            continue  # incomplete scan
        if "incomplete" in r.evidence:
            continue
        old = current.get(r.metric)
        if old is None or r.value < old:
            current[r.metric] = r.value
            changed[r.metric] = (old, r.value)
    if changed:
        payload = {"_comment": "Ratchet: tooling only lowers these. Raising one is a reviewed human edit.",
                   "metrics": dict(sorted(current.items()))}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return changed
