"""Saleha Tests: Multi-File Cross-Module Interface Propagation & Sandbox Mock Synthesizer.

Verifies:
1. MultiFileInterfacePropagator: Cross-file AST call site rewriting across modules.
2. Two-Phase Commit (2PC): Atomic rollback to checkpoint when verification test fails.
3. SandboxMockSynthesizer: Offline execution of requests, boto3, stripe, and redis inside hardware sandbox.
4. MultiFilePRM: Step-level cross-module consistency scoring.
"""

from pathlib import Path
import pytest

from saleha.core.agent_pc import AgentPC
from saleha.core.multi_file_interface_propagator import (
    MultiFileInterfacePropagator,
    SignatureDelta,
    PropagationResult,
)
from saleha.core.sandbox_mock_synthesizer import (
    SandboxMockSynthesizer,
    VIRTUAL_MOCK_PRELUDE,
)
from saleha.core.alignment.multi_file_prm import (
    MultiFilePRM,
    MultiFilePRMScore,
)
from saleha.core.windows_job_sandbox import WindowsJobSandbox


# ==============================================================================
# 1. Multi-File Interface Propagation (2PC Atomic Commit)
# ==============================================================================

def test_cross_file_signature_propagation_success(tmp_path: Path) -> None:
    pc = AgentPC(agent_role="multi_file_test", base_dir=tmp_path / "workspace")
    propagator = MultiFileInterfacePropagator(pc=pc)

    # 1. Callee definition
    callee_code = """
def calculate_discount(price: float, discount_rate: float) -> float:
    return price * (1.0 - discount_rate)
"""
    # 2. Caller 1
    caller1_code = """
from math_ops import calculate_discount

def process_order(price: float) -> float:
    return calculate_discount(price, rate=0.10)
"""
    # 3. Caller 2
    caller2_code = """
from math_ops import calculate_discount

def generate_invoice(item_price: float) -> float:
    return calculate_discount(item_price, rate=0.20)
"""
    # 4. Verification test
    test_code = """
from order_service import process_order
from invoice_service import generate_invoice

assert process_order(100.0) == 90.0
assert generate_invoice(100.0) == 80.0
"""
    pc.write_in_pc("math_ops.py", callee_code)
    pc.write_in_pc("order_service.py", caller1_code)
    pc.write_in_pc("invoice_service.py", caller2_code)
    pc.write_in_pc("test_all.py", test_code)

    # Propagate parameter rename: 'rate' -> 'discount_rate'
    delta = SignatureDelta(
        symbol_name="calculate_discount",
        old_args=["price", "rate"],
        new_args=["price", "discount_rate"],
        renamed_args={"rate": "discount_rate"},
    )

    result: PropagationResult = propagator.propagate_signature_change(
        delta=delta,
        verification_test_files=["test_all.py"],
    )

    assert result.success is True
    assert result.rolled_back is False
    assert len(result.files_updated) == 2
    assert "order_service.py" in result.files_updated
    assert "invoice_service.py" in result.files_updated

    # Verify that code in caller files has been rewritten to discount_rate
    content1 = pc.workspace.read_file("order_service.py")
    content2 = pc.workspace.read_file("invoice_service.py")
    assert "discount_rate=0.1" in content1
    assert "discount_rate=0.2" in content2


def test_cross_file_2pc_rollback_on_test_failure(tmp_path: Path) -> None:
    pc = AgentPC(agent_role="rollback_test", base_dir=tmp_path / "rollback_ws")
    propagator = MultiFileInterfacePropagator(pc=pc)

    caller_code = """
from service import execute_task

def run():
    return execute_task(param=123)
"""
    failing_test_code = """
from caller import run
assert False, "Verification test fails intentionally"
"""
    pc.write_in_pc("caller.py", caller_code)
    pc.write_in_pc("test_fail.py", failing_test_code)

    delta = SignatureDelta(
        symbol_name="execute_task",
        old_args=["param"],
        new_args=["new_param"],
        renamed_args={"param": "new_param"},
    )

    result = propagator.propagate_signature_change(
        delta=delta,
        verification_test_files=["test_fail.py"],
    )

    # 2PC must abort and roll back all files
    assert result.success is False
    assert result.rolled_back is True
    assert "Verification test test_fail.py failed" in result.error_message

    # Verify that caller.py was restored to original content
    restored_content = pc.workspace.read_file("caller.py")
    assert "param=123" in restored_content


# ==============================================================================
# 2. Autonomous Sandbox Mock Synthesizer (Offline Execution)
# ==============================================================================

def test_sandbox_mock_synthesizer_offline_execution() -> None:
    synthesizer = SandboxMockSynthesizer()

    # Code that calls multiple external services (requests, stripe, boto3, redis)
    code_with_externals = """
import requests
import stripe
import boto3
import redis

def sync_payment_and_cloud_state(user_id: str, amount: int) -> dict:
    # 1. HTTP call to external API
    resp = requests.get("https://api.external.com/users/" + user_id)
    assert resp.status_code == 200
    assert resp.ok is True

    # 2. Stripe charge
    charge = stripe.Charge.create(amount=amount, currency="usd")
    assert charge["status"] == "succeeded"

    # 3. AWS S3 check
    s3 = boto3.client("s3")
    objs = s3.list_objects_v2(Bucket="test-bucket")
    assert len(objs["Contents"]) > 0

    # 4. Redis in-memory cache
    r = redis.Redis()
    r.set(f"user:{user_id}:paid", "true")
    assert r.get(f"user:{user_id}:paid") == b"true"

    return {
        "status": "PROCESSED",
        "charge_id": charge["id"],
        "cached": True,
    }

# Execute function and assert
res = sync_payment_and_cloud_state("usr_456", 2500)
assert res["status"] == "PROCESSED"
assert res["cached"] is True
"""
    # Detect external dependencies
    deps = synthesizer.detect_external_dependencies(code_with_externals)
    assert "requests" in deps
    assert "stripe" in deps
    assert "boto3" in deps
    assert "redis" in deps

    # Inject mock prelude
    injected_code = synthesizer.inject_virtual_mocks(code_with_externals)

    # Run in isolated physical Win32 Job Object sandbox
    sandbox = WindowsJobSandbox(memory_limit_mb=100, timeout_ms=5000)
    run_res = sandbox.run_isolated_python_snippet(injected_code)

    # Must pass cleanly without any internet or real cloud credentials
    assert run_res.passed is True
    assert run_res.exit_code == 0
    assert run_res.timed_out is False


# ==============================================================================
# 3. Multi-File PRM Consistency Scoring
# ==============================================================================

def test_multi_file_prm_consistency_scoring() -> None:
    prm = MultiFilePRM()

    # Consistent cluster
    valid_cluster = {
        "service.py": """
def get_user_profile(user_id: int) -> dict:
    return {"id": user_id, "name": "Alice"}
""",
        "controller.py": """
from service import get_user_profile

def render_view(uid: int) -> dict:
    return get_user_profile(uid)
"""
    }

    score: MultiFilePRMScore = prm.evaluate_file_cluster(valid_cluster)
    assert score.is_valid is True
    assert score.composite_score >= 0.8
    assert score.import_coherence == 1.0
    assert score.signature_alignment == 1.0
    assert len(score.diagnostics) == 0

    # Inconsistent cluster (unrecognized kwargs)
    broken_cluster = {
        "service.py": """
def process_data(data: list) -> bool:
    return len(data) > 0
""",
        "consumer.py": """
from service import process_data

def run():
    return process_data(data=[], invalid_kwarg=True)
"""
    }

    broken_score = prm.evaluate_file_cluster(broken_cluster)
    assert broken_score.is_valid is False
    assert len(broken_score.diagnostics) > 0


def test_multi_file_prm_flags_import_of_undefined_symbol() -> None:
    cluster = {
        "service.py": "def get_user(uid: int) -> dict:\n    return {}\n",
        "controller.py": "import json\nfrom service import get_account\n",
    }

    score = MultiFilePRM().evaluate_file_cluster(cluster)

    assert score.import_coherence == 0.0
    assert score.is_valid is False
    assert any("get_account" in d for d in score.diagnostics)
