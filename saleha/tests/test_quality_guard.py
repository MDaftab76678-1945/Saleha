"""
Unit tests for Saleha Quality Guard (saleha/core/quality_guard.py).
Validates AST syntax checking, type coverage calculation, cognitive nesting,
and workspace auditing.

The "sovereign brand hygiene" rule (SOV-001) was removed: it matched the bare
words "claude", "hermes" and "kimi" anywhere in a file and raised a CRITICAL
that failed it. Two of those three words appear nowhere else in this
repository.
"""

import tempfile
from saleha.core.quality_guard import QualityGuard, QualityReport, QualityIssue, quality_guard


def test_clean_code_passes() -> None:
    guard = QualityGuard()
    code = '''
def add_numbers(a: int, b: int) -> int:
    """Adds two integers."""
    return a + b
'''
    report = guard.check_code(code)
    assert report.passed is True
    assert report.quality_score >= 95.0
    assert report.critical_count == 0
    assert report.total_functions == 1
    assert report.typed_functions == 1
    assert report.type_coverage_pct == 100.0


def test_syntax_error_detected() -> None:
    guard = QualityGuard()
    code = '''
def broken_syntax(
    return "missing parenthesis"
'''
    report = guard.check_code(code)
    assert report.passed is False
    assert report.quality_score == 0.0
    assert report.critical_count >= 1
    assert any(i.rule_id == "SYNTAX-001" for i in report.issues)


def test_eval_exec_detected() -> None:
    guard = QualityGuard()
    code = '''
def run_dangerous(payload: str) -> None:
    eval(payload)
'''
    report = guard.check_code(code)
    assert any(i.rule_id == "SEC-001" for i in report.issues)
    assert report.critical_count >= 1
    assert report.passed is False


def test_naked_except_detected() -> None:
    guard = QualityGuard()
    code = '''
def handle_error(val: int) -> int:
    try:
        return 10 // val
    except:
        return 0
'''
    report = guard.check_code(code)
    assert any(i.rule_id == "ERR-001" for i in report.issues)
    assert report.major_count >= 1


def test_the_brand_rule_is_gone() -> None:
    """
    SOV-001 matched the bare words "claude", "hermes" and "kimi" anywhere in a
    file and raised a CRITICAL that failed it. Ordinary code posting to a
    local model scored 80.0 and passed=False.

    ttc_solver ranks candidate solutions by this score, so a correct candidate
    could lose to a worse one for naming the model it calls. And "hermes" and
    "kimi" appear nowhere else in this repository -- the word list came from
    another project.
    """
    guard = QualityGuard()
    code = '''
import requests

def fetch(prompt: str) -> str:
    r = requests.post("http://localhost:11434/api/generate",
                      json={"model": "claude-opus-5", "prompt": prompt})
    return r.json()["response"]
'''
    report = guard.check_code(code)
    assert not any(i.rule_id == "SOV-001" for i in report.issues)
    assert report.passed is True
    assert report.quality_score == 100.0


def test_no_rule_scores_a_file_on_what_its_strings_say() -> None:
    """Naming any product, in any form, is not a quality defect."""
    guard = QualityGuard()
    samples = [
        'NAME = "powered by Hermes"\n',
        'MODEL = "kimi-k2"\n',
        'def hi() -> str:\n    return "I am Claude"\n',
    ]
    for text in samples:
        report = guard.check_code(text)
        assert not any(i.rule_id == "SOV-001" for i in report.issues), text


def test_raw_score_survives_the_clamp() -> None:
    """
    quality_score clamps at 0.0, so 25 untyped functions and 400 looked
    identical. raw_score keeps them apart for callers that rank candidates.
    """
    guard = QualityGuard()
    def untyped(count: int) -> str:
        return "".join(f"def f{i}(a):\n    return a\n" for i in range(count))

    small = guard.check_code(untyped(30))
    large = guard.check_code(untyped(200))
    assert small.quality_score == large.quality_score == 0.0
    assert small.raw_score > large.raw_score


def test_type_coverage_calculation() -> None:
    guard = QualityGuard()
    code = '''
def typed_func(x: int) -> int:
    return x * 2

def untyped_func(x, y):
    return x + y
'''
    report = guard.check_code(code)
    assert report.total_functions == 2
    assert report.typed_functions == 1
    assert report.type_coverage_pct == 50.0
    assert any(i.rule_id == "TYPE-001" for i in report.issues)


def test_nesting_depth_detection() -> None:
    guard = QualityGuard()
    code = '''
def deeply_nested() -> None:
    if True:
        for i in range(10):
            while False:
                try:
                    if True:
                        print("Too deep")
                except Exception:
                    pass
'''
    report = guard.check_code(code)
    assert report.max_nesting_depth >= 5
    assert any(i.rule_id == "COMPLEX-001" for i in report.issues)


def test_check_file_and_workspace() -> None:
    guard = QualityGuard()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
        tf.write('''
def sample(x: int) -> int:
    return x * 2
''')
        temp_path = tf.name

    report = guard.check_file(temp_path)
    assert report.passed is True
    assert report.file_path == temp_path

    # Workspace check
    summary = guard.check_workspace(root_dir="saleha/core", max_files=5)
    assert summary["files_analyzed"] > 0
    assert "files_found" in summary
    assert "scan_is_complete" in summary
    assert "average_quality_score" in summary
    assert "average_type_coverage_pct" in summary


def test_undefined_name_detected_on_missing_import() -> None:
    guard = QualityGuard()
    # Exactly replicates the defect where Set was used without importing from typing
    code = '''
from typing import Dict, Any, Optional, List, Tuple

def get_tool_names() -> Set[str]:
    return {"a", "b"}
'''
    report = guard.check_code(code)
    assert report.passed is False
    assert report.critical_count >= 1
    undef_issues = [i for i in report.issues if i.rule_id == "UNDEF-001"]
    assert len(undef_issues) >= 1
    assert any("Set" in i.message for i in undef_issues)


def test_undefined_name_detected_on_undefined_variable() -> None:
    guard = QualityGuard()
    code = '''
def calculate() -> int:
    return unimported_var + 10
'''
    report = guard.check_code(code)
    assert report.passed is False
    assert any(i.rule_id == "UNDEF-001" and "unimported_var" in i.message for i in report.issues)


def test_valid_imports_pass_undef_check() -> None:
    guard = QualityGuard()
    code = '''
from typing import Dict, Any, Optional, List, Tuple, Set

def get_tool_names() -> Set[str]:
    tools: Set[str] = set()
    return tools
'''
    report = guard.check_code(code)
    assert report.passed is True
    assert not any(i.rule_id == "UNDEF-001" for i in report.issues)


def test_scope_leakage_prevented_in_nested_functions() -> None:
    """Inner function bindings must NOT hoist into outer function scope."""
    guard = QualityGuard()
    code = '''
def outer_func() -> int:
    def inner_func() -> int:
        inner_var = 10
        return inner_var
    return inner_var + 5  # inner_var is undefined in outer_func!
'''
    report = guard.check_code(code)
    assert report.passed is False
    assert any(i.rule_id == "UNDEF-001" and "inner_var" in i.message for i in report.issues)


def test_comprehension_scope_isolation() -> None:
    """Python 3 comprehension loop variables must NOT leak into the enclosing function."""
    guard = QualityGuard()
    code = '''
def calculate_data() -> int:
    squares = [x * x for x in range(10)]
    return x  # x is undefined outside the comprehension!
'''
    report = guard.check_code(code)
    assert report.passed is False
    assert any(i.rule_id == "UNDEF-001" and "x" in i.message for i in report.issues)


def test_chained_generator_later_clause_sees_earlier_target() -> None:
    """A second `for`/`if` clause in the same comprehension can reference a
    name bound by an earlier clause (real Python scoping) -- this was a
    false positive found in saleha/server/web_server.py's real code:
    `set(t for e in entries for t in e.get("tags", []))` flagged `e` as
    CRITICAL undefined, because the old _visit_comprehension visited every
    generator's `iter` in one pass before any generator's target entered
    scope, instead of interleaving iter-then-target left to right."""
    guard = QualityGuard()
    code = '''
def tag_count(entries: list) -> int:
    return len(set(t for e in entries for t in e.get("tags", [])))
'''
    report = guard.check_code(code)
    assert report.critical_count == 0
    assert not any(i.rule_id == "UNDEF-001" for i in report.issues)


def test_first_generator_iter_cannot_see_later_bound_names() -> None:
    """The first generator's `iter` runs in the enclosing scope, before any
    comprehension target is bound -- it must not see a name bound later in
    the same comprehension. Guards against over-fixing the case above into
    a scope that is too permissive."""
    guard = QualityGuard()
    code = '''
def broken() -> list:
    return [x for x in undefined_source for y in x]
'''
    report = guard.check_code(code)
    assert report.critical_count > 0
    assert any(i.rule_id == "UNDEF-001" and "undefined_source" in i.message for i in report.issues)


def test_nesting_depth_isolated_from_inner_functions() -> None:
    """Outer function with zero nesting must NOT be penalized for inner function's nesting depth."""
    guard = QualityGuard()
    code = '''
def outer_clean() -> None:
    def inner_deep() -> None:
        if True:
            for i in range(5):
                while False:
                    try:
                        if True:
                            pass
                    except Exception:
                        pass
    inner_deep()
'''
    report = guard.check_code(code)
    # The warning COMPLEX-001 should only target inner_deep, NOT outer_clean
    complex_issues = [i for i in report.issues if i.rule_id == "COMPLEX-001"]
    assert len(complex_issues) == 1
    assert "inner_deep" in complex_issues[0].message
    assert "outer_clean" not in complex_issues[0].message


def test_module_level_except_name_not_falsely_undefined() -> None:
    """`except X as name:` at module scope must not score `name` as undefined.

    ast.ExceptHandler is not an ast.stmt, so a plain `isinstance(child,
    ast.stmt)` filter over a Try node's children silently skipped every
    handler -- found via saleha/core/inference_router_bridge.py, a real
    file in this codebase, being scored CRITICAL for `str(exc)` inside
    `except ImportError as exc:` at module level.
    """
    guard = QualityGuard()
    code = '''
try:
    import foo
except ImportError as exc:
    err = str(exc)
'''
    report = guard.check_code(code)
    assert not any(i.rule_id == "UNDEF-001" for i in report.issues)


def test_varargs_untyped_counted_in_coverage() -> None:
    """Functions with untyped *args or **kwargs must NOT be marked fully typed."""
    guard = QualityGuard()
    code = '''
def func_untyped_args(x: int, *args, **kwargs) -> int:
    return x
'''
    report = guard.check_code(code)
    assert report.typed_functions == 0
    assert any(i.rule_id == "TYPE-001" for i in report.issues)


def test_lambda_parameter_is_not_undefined() -> None:
    """
    Found while auditing saleha/tools/base.py: `lambda params: self.execute(**params)`
    scored a CRITICAL UNDEF-001 on 'params' and failed the file, because
    ScopeVisitor had no visit_Lambda -- it fell through to generic_visit,
    which walks straight into the lambda body without ever putting the
    lambda's own parameters into scope.
    """
    guard = QualityGuard()
    code = '''
def to_dict() -> dict:
    return {"handler": lambda params: params}
'''
    report = guard.check_code(code)
    assert report.passed is True
    assert not any(i.rule_id == "UNDEF-001" for i in report.issues)


def test_lambda_parameter_does_not_leak_outside_lambda() -> None:
    """A lambda's parameters must stay scoped to the lambda body."""
    guard = QualityGuard()
    code = '''
def make() -> int:
    f = lambda x: x + 1
    return x
'''
    report = guard.check_code(code)
    assert report.passed is False
    assert any(i.rule_id == "UNDEF-001" and "x" in i.message for i in report.issues)


def test_real_undefined_name_inside_lambda_is_still_caught() -> None:
    """The lambda scope fix must not make UNDEF-001 blind to real defects inside lambdas."""
    guard = QualityGuard()
    code = '''
f = lambda x: x + totally_undefined_name
'''
    report = guard.check_code(code)
    assert report.passed is False
    assert any(i.rule_id == "UNDEF-001" and "totally_undefined_name" in i.message for i in report.issues)


def test_main_guard_block_assignment_is_not_undefined() -> None:
    """
    Found auditing Gemini's Round 10 files: EVERY `if __name__ == "__main__":`
    demo block in saleha/orchestrator.py, code_executor.py, tester.py, and
    reviewer.py scored a false CRITICAL UNDEF-001 on every name it assigned.

    Root cause: `if` is not a new scope in Python (unlike a function or
    class), so `if __name__ == "__main__": x = 1` binds `x` at module level.
    The old code only scanned direct top-level statements for bindings, never
    descending into an `if` block's body, so every such assignment looked
    undefined the moment it was referenced.
    """
    guard = QualityGuard()
    code = '''
if __name__ == "__main__":
    result = 5
    print(result)
'''
    report = guard.check_code(code)
    assert report.passed is True
    assert not any(i.rule_id == "UNDEF-001" for i in report.issues)


def test_function_scope_does_not_leak_through_module_level_if() -> None:
    """A function defined inside a module-level `if` block still opens its
    own scope -- its locals must not leak to module level."""
    guard = QualityGuard()
    code = '''
if True:
    def f() -> int:
        local_var = 1
        return local_var
print(local_var)
'''
    report = guard.check_code(code)
    assert report.passed is False
    assert any(i.rule_id == "UNDEF-001" and "local_var" in i.message for i in report.issues)


def test_try_except_and_for_loop_bindings_at_module_level() -> None:
    """Exception names and for-loop variables bound inside a module-level
    try/for block must be visible afterward, same as real Python scoping."""
    try_code = '''
try:
    import json
except ImportError:
    json = None
print(json)
'''
    for_code = '''
for item in range(10):
    pass
print(item)
'''
    assert quality_guard.check_code(try_code).passed is True
    assert quality_guard.check_code(for_code).passed is True
