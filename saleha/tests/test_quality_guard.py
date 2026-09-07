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


def test_clean_code_passes():
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


def test_syntax_error_detected():
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


def test_eval_exec_detected():
    guard = QualityGuard()
    code = '''
def run_dangerous(payload: str) -> None:
    eval(payload)
'''
    report = guard.check_code(code)
    assert any(i.rule_id == "SEC-001" for i in report.issues)
    assert report.critical_count >= 1
    assert report.passed is False


def test_naked_except_detected():
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


def test_the_brand_rule_is_gone():
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


def test_no_rule_scores_a_file_on_what_its_strings_say():
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


def test_raw_score_survives_the_clamp():
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


def test_type_coverage_calculation():
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


def test_nesting_depth_detection():
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


def test_check_file_and_workspace():
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
