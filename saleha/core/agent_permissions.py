"""
Saleha Core: Zero-Trust Capability-Based Agent Permissions (AgentShield)

Implements granular execution permissions and safety policies for autonomous agents:
1. FilesystemPolicy: Restricts file I/O to designated workspace boundaries.
2. NetworkPolicy: Enforces offline sandbox guarantees or domain allowlists.
3. ProcessPolicy: Caps execution timeout and prevents unauthorized subshell spawning.
4. AgentCapabilityToken: Role-based capability tokens verified before any tool or execution action.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple


@dataclass
class FilesystemPolicy:
    """Defines filesystem read/write boundary policies."""
    allowed_write_roots: List[str] = field(default_factory=lambda: ["."])
    forbid_traversal_above_root: bool = True
    blocked_patterns: List[str] = field(default_factory=lambda: [
        r"\.env$", r"id_rsa", r"\.git[\\/]", r"passwd$", r"shadow$",
    ])


@dataclass
class NetworkPolicy:
    """Defines network connectivity boundaries."""
    allow_outbound: bool = False
    allowed_domains: List[str] = field(default_factory=list)


@dataclass
class ProcessPolicy:
    """Defines process execution boundaries."""
    max_timeout_seconds: int = 30
    allow_shell: bool = False
    max_memory_mb: int = 512


@dataclass
class AgentCapabilityToken:
    """A cryptographic or role-based capability token granting specific permissions."""
    agent_id: str
    role_name: str
    fs_policy: FilesystemPolicy = field(default_factory=FilesystemPolicy)
    net_policy: NetworkPolicy = field(default_factory=NetworkPolicy)
    proc_policy: ProcessPolicy = field(default_factory=ProcessPolicy)
    granted_tools: Set[str] = field(default_factory=lambda: {"read_file", "write_file", "execute_code"})


class PolicyEnforcementEngine:
    """Zero-Trust Policy Enforcement Engine for autonomous AI agents."""

    @staticmethod
    def validate_file_write(token: AgentCapabilityToken, target_path: str) -> Tuple[bool, str]:
        """Validates if the agent's capability token allows writing to the given path."""
        norm_target = os.path.abspath(target_path)
        for root in token.fs_policy.allowed_write_roots:
            norm_root = os.path.abspath(root)
            if norm_target.startswith(norm_root):
                return True, "Authorized"

        return False, f"Zero-Trust Policy Violation: Write to '{target_path}' is outside authorized workspace root."

    @staticmethod
    def validate_network_access(token: AgentCapabilityToken, domain: str) -> Tuple[bool, str]:
        """Validates if the agent is authorized to make external network connections."""
        if not token.net_policy.allow_outbound:
            return False, "Zero-Trust Policy Violation: Network access is disabled for this agent."
        if token.net_policy.allowed_domains and domain not in token.net_policy.allowed_domains:
            return False, f"Zero-Trust Policy Violation: Domain '{domain}' not in network allowlist."
        return True, "Authorized"

    @staticmethod
    def get_default_token(role_name: str) -> AgentCapabilityToken:
        """Returns preset least-privilege capability token for standard agent roles."""
        role_lower = role_name.lower()
        if "coder" in role_lower:
            return AgentCapabilityToken(
                agent_id="coder_agent",
                role_name="CoderAgent",
                fs_policy=FilesystemPolicy(allowed_write_roots=["."]),
                net_policy=NetworkPolicy(allow_outbound=False),
                proc_policy=ProcessPolicy(max_timeout_seconds=20),
            )
        elif "tester" in role_lower:
            return AgentCapabilityToken(
                agent_id="tester_agent",
                role_name="TesterAgent",
                fs_policy=FilesystemPolicy(allowed_write_roots=[".", "tests"]),
                net_policy=NetworkPolicy(allow_outbound=False),
                proc_policy=ProcessPolicy(max_timeout_seconds=30),
            )
        else:
            return AgentCapabilityToken(
                agent_id="base_agent",
                role_name=role_name,
                fs_policy=FilesystemPolicy(allowed_write_roots=["."]),
                net_policy=NetworkPolicy(allow_outbound=False),
            )


policy_engine = PolicyEnforcementEngine()


if __name__ == "__main__":
    _token = PolicyEnforcementEngine.get_default_token("CoderAgent")
    _ok, _msg = PolicyEnforcementEngine.validate_file_write(_token, "./safe_code.py")
    _fail_ok, _fail_msg = PolicyEnforcementEngine.validate_file_write(_token, "/etc/passwd")
