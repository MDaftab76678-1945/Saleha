"""
Unit Tests for ExecutionPolicy & Container Sandbox Backend Policy.

Verifies:
1. Environment mode parsing & alias resolution (auto, local, docker, require-docker).
2. Docker daemon probing, caching, and cache reset isolation.
3. Fail-closed invariant for require-docker when daemon is unreachable.
4. Degradation behavior for docker mode when daemon is unreachable.
5. Container command hardening (--network none, --pids-limit, resource caps, volume mount).
6. ExecutionPolicy class methods and PolicyDecision evaluation.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from saleha.core.execution_policy import (
    ExecutionPolicy,
    PolicyDecision,
    _reset_probe_cache,
    build_docker_command,
    docker_available,
    get_sandbox_mode,
    resolve_backend,
)


def test_get_sandbox_mode_defaults_and_aliases() -> None:
    prev = os.environ.get("SALEHA_SANDBOX")
    try:
        # Default
        os.environ.pop("SALEHA_SANDBOX", None)
        assert get_sandbox_mode() == "auto"

        # Explicit standard values
        os.environ["SALEHA_SANDBOX"] = "local"
        assert get_sandbox_mode() == "local"

        os.environ["SALEHA_SANDBOX"] = "docker"
        assert get_sandbox_mode() == "docker"

        os.environ["SALEHA_SANDBOX"] = "require-docker"
        assert get_sandbox_mode() == "require-docker"

        # Aliases
        os.environ["SALEHA_SANDBOX"] = "strict"
        assert get_sandbox_mode() == "require-docker"

        os.environ["SALEHA_SANDBOX"] = "subprocess"
        assert get_sandbox_mode() == "local"

        os.environ["SALEHA_SANDBOX"] = "invalid_mode_value"
        assert get_sandbox_mode() == "auto"
    finally:
        if prev is None:
            os.environ.pop("SALEHA_SANDBOX", None)
        else:
            os.environ["SALEHA_SANDBOX"] = prev


def test_docker_available_caching_and_reset() -> None:
    _reset_probe_cache()
    with patch("shutil.which", return_value=None):
        assert docker_available() is False

    # Second call should use cache
    assert docker_available() is False

    # Reset cache and mock available
    _reset_probe_cache()
    with patch("shutil.which", return_value="/usr/bin/docker"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            assert docker_available(force_refresh=True) is True


def test_resolve_backend_modes_with_mock() -> None:
    prev = os.environ.get("SALEHA_SANDBOX")
    try:
        # 1. Local / Auto mode always returns subprocess
        os.environ["SALEHA_SANDBOX"] = "local"
        backend, reason = resolve_backend()
        assert backend == "subprocess"
        assert "subprocess" in reason

        # 2. Docker mode when Docker is DOWN -> degrade to subprocess
        os.environ["SALEHA_SANDBOX"] = "docker"
        with patch("saleha.core.execution_policy.docker_available", return_value=False):
            backend, reason = resolve_backend()
            assert backend == "subprocess"
            assert "degraded" in reason

        # 3. Docker mode when Docker is UP -> docker
        with patch("saleha.core.execution_policy.docker_available", return_value=True):
            backend, reason = resolve_backend()
            assert backend == "docker"

        # 4. Require-docker mode when Docker is DOWN -> fail closed ('none')
        os.environ["SALEHA_SANDBOX"] = "require-docker"
        with patch("saleha.core.execution_policy.docker_available", return_value=False):
            backend, reason = resolve_backend()
            assert backend == "none"
            assert "refused" in reason

        # 5. Require-docker mode when Docker is UP -> docker
        with patch("saleha.core.execution_policy.docker_available", return_value=True):
            backend, reason = resolve_backend()
            assert backend == "docker"
    finally:
        if prev is None:
            os.environ.pop("SALEHA_SANDBOX", None)
        else:
            os.environ["SALEHA_SANDBOX"] = prev


def test_build_docker_command_hardening() -> None:
    cmd = build_docker_command(
        host_script_path="scripts/run_audit.py",
        image="python:3.12-slim",
        memory="256m",
        cpus="0.5",
        pids_limit=64,
        custom_args=["--verbose", "--flag"],
    )

    # Security boundaries verification
    assert "--network" in cmd
    assert "none" in cmd[cmd.index("--network") + 1]
    assert "--security-opt" in cmd
    assert "no-new-privileges" in cmd[cmd.index("--security-opt") + 1]
    assert "--memory" in cmd
    assert "256m" in cmd[cmd.index("--memory") + 1]
    assert "--cpus" in cmd
    assert "0.5" in cmd[cmd.index("--cpus") + 1]
    assert "--pids-limit" in cmd
    assert "64" in cmd[cmd.index("--pids-limit") + 1]

    # Workspace mount verification
    assert "-v" in cmd
    assert "-w" in cmd
    assert "/sandbox" in cmd[cmd.index("-w") + 1]

    # Custom args verification
    assert "--verbose" in cmd
    assert "--flag" in cmd


def test_execution_policy_class() -> None:
    policy = ExecutionPolicy(
        mode="local",
        memory="1g",
        cpus="2.0",
        pids_limit=256,
    )

    assert policy.get_mode() == "local"
    assert policy.memory == "1g"
    assert policy.cpus == "2.0"
    assert policy.pids_limit == 256

    backend, _ = policy.resolve_backend()
    assert backend == "subprocess"

    cmd = policy.build_command("app/main.py", custom_args=["--test"])
    assert cmd == ["python", "app/main.py", "--test"]

    decision: PolicyDecision = policy.evaluate_policy("app/main.py")
    assert decision.backend == "subprocess"
    assert decision.sandbox_mode == "local"
    assert decision.command == ["python", "app/main.py"]


def test_execution_policy_fail_closed_decision() -> None:
    policy = ExecutionPolicy(mode="require-docker")
    with patch.object(policy, "is_docker_available", return_value=False):
        decision: PolicyDecision = policy.evaluate_policy("app/critical.py")
        assert decision.backend == "none"
        assert decision.sandbox_mode == "require-docker"
        assert decision.command is None
        assert "refused" in decision.reason
