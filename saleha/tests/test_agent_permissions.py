"""Unit tests for Zero-Trust Capability-Based Agent Permissions."""

import unittest
import os
from saleha.core.agent_permissions import (
    PolicyEnforcementEngine,
    AgentCapabilityToken,
    FilesystemPolicy,
    NetworkPolicy,
    ProcessPolicy,
)


class TestAgentPermissions(unittest.TestCase):
    """Test suite for Zero-Trust Policy Enforcement Engine."""

    def test_default_coder_token_has_proper_boundaries(self):
        token = PolicyEnforcementEngine.get_default_token("CoderAgent")
        self.assertEqual(token.role_name, "CoderAgent")
        self.assertFalse(token.net_policy.allow_outbound)
        self.assertEqual(token.proc_policy.max_timeout_seconds, 20)

    def test_validate_file_write_authorized(self):
        token = PolicyEnforcementEngine.get_default_token("CoderAgent")
        allowed, reason = PolicyEnforcementEngine.validate_file_write(token, "./src/main.py")
        self.assertTrue(allowed)
        self.assertEqual(reason, "Authorized")

    def test_validate_file_write_unauthorized_traversal(self):
        token = AgentCapabilityToken(
            agent_id="test_agent",
            role_name="TestAgent",
            fs_policy=FilesystemPolicy(allowed_write_roots=["./sandbox"]),
        )
        allowed, reason = PolicyEnforcementEngine.validate_file_write(token, "../etc/shadow")
        self.assertFalse(allowed)
        self.assertIn("Zero-Trust Policy Violation", reason)

    def test_validate_network_access_enforcement(self):
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


if __name__ == "__main__":
    unittest.main()
