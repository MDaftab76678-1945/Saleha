"""Unit tests for Zero-Trust Capability-Based Agent Permissions."""

from __future__ import annotations

import unittest
from saleha.core.agent_permissions import (
    PolicyEnforcementEngine,
    AgentCapabilityToken,
    FilesystemPolicy,
    NetworkPolicy,
    ProcessPolicy,
)


class TestAgentPermissions(unittest.TestCase):
    """Test suite for Zero-Trust Policy Enforcement Engine."""

    def test_default_coder_token_has_proper_boundaries(self) -> None:
        token = PolicyEnforcementEngine.get_default_token("CoderAgent")
        self.assertEqual(token.role_name, "CoderAgent")
        self.assertFalse(token.net_policy.allow_outbound)
        self.assertEqual(token.proc_policy.max_timeout_seconds, 20)

    def test_validate_file_write_authorized(self) -> None:
        token = PolicyEnforcementEngine.get_default_token("CoderAgent")
        allowed, reason = PolicyEnforcementEngine.validate_file_write(token, "./src/main.py")
        self.assertTrue(allowed)
        self.assertEqual(reason, "Authorized")

    def test_validate_file_write_blocked_patterns(self) -> None:
        token = PolicyEnforcementEngine.get_default_token("CoderAgent")
        # Writing to .env should be blocked even inside allowed root
        allowed_env, reason_env = PolicyEnforcementEngine.validate_file_write(token, "./.env")
        self.assertFalse(allowed_env)
        self.assertIn("matches blocked pattern", reason_env)

        # Writing to id_rsa should be blocked
        allowed_key, reason_key = PolicyEnforcementEngine.validate_file_write(token, "./secrets/id_rsa")
        self.assertFalse(allowed_key)
        self.assertIn("matches blocked pattern", reason_key)

        # Writing to .git/config should be blocked
        allowed_git, reason_git = PolicyEnforcementEngine.validate_file_write(token, "./.git/config")
        self.assertFalse(allowed_git)
        self.assertIn("matches blocked pattern", reason_git)

    def test_validate_file_write_unauthorized_traversal(self) -> None:
        token = AgentCapabilityToken(
            agent_id="test_agent",
            role_name="TestAgent",
            fs_policy=FilesystemPolicy(allowed_write_roots=["./sandbox"]),
        )
        allowed, reason = PolicyEnforcementEngine.validate_file_write(token, "../etc/shadow")
        self.assertFalse(allowed)
        self.assertIn("Zero-Trust Policy Violation", reason)

    def test_validate_network_access_enforcement(self) -> None:
        token = PolicyEnforcementEngine.get_default_token("CoderAgent")
        allowed, reason = PolicyEnforcementEngine.validate_network_access(token, "api.openai.com")
        self.assertFalse(allowed)
        self.assertIn("Network access is disabled", reason)

        # Allow specific domain
        token.net_policy.allow_outbound = True
        token.net_policy.allowed_domains = ["localhost", "127.0.0.1"]
        allowed_local, _ = PolicyEnforcementEngine.validate_network_access(token, "localhost")
        self.assertTrue(allowed_local)

        blocked_ext, _ = PolicyEnforcementEngine.validate_network_access(token, "evil.com")
        self.assertFalse(blocked_ext)

    def test_validate_tool_access(self) -> None:
        token = AgentCapabilityToken(
            agent_id="test_agent",
            role_name="TestAgent",
            granted_tools={"read_file", "write_file"},
        )
        allowed_read, reason_read = PolicyEnforcementEngine.validate_tool_access(token, "read_file")
        self.assertTrue(allowed_read)
        self.assertEqual(reason_read, "Authorized")

        allowed_exec, reason_exec = PolicyEnforcementEngine.validate_tool_access(token, "shell_exec")
        self.assertFalse(allowed_exec)
        self.assertIn("not in granted capabilities", reason_exec)

    def test_validate_process_execution(self) -> None:
        token = AgentCapabilityToken(
            agent_id="test_agent",
            role_name="TestAgent",
            proc_policy=ProcessPolicy(max_timeout_seconds=15, allow_shell=False),
        )
        # Normal command within timeout
        ok_cmd, _ = PolicyEnforcementEngine.validate_process_execution(token, "python -c 'print(1)'", requested_timeout=10)
        self.assertTrue(ok_cmd)

        # Timeout exceeding limit
        timeout_fail, timeout_reason = PolicyEnforcementEngine.validate_process_execution(token, "python worker.py", requested_timeout=30)
        self.assertFalse(timeout_fail)
        self.assertIn("exceeds maximum allowed limit", timeout_reason)

        # Shell chaining attempt when allow_shell is False
        shell_fail, shell_reason = PolicyEnforcementEngine.validate_process_execution(token, "python script.py && rm -rf /")
        self.assertFalse(shell_fail)
        self.assertIn("Shell metacharacters not permitted", shell_reason)


if __name__ == "__main__":
    unittest.main()
