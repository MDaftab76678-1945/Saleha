"""
Saleha Core: Ephemeral Vault Secret & Env Sync Bridge

Injects encrypted credentials directly from EncryptedVault into ephemeral subprocess
environments without saving plain-text .env secret files to disk.
"""

from __future__ import annotations

import os
import subprocess
from typing import Dict, List, Optional, Tuple, Any

from saleha.core.vault import EncryptedVault, DEFAULT_VAULT_PATH


class EnvSyncBridge:
    """Provides secure zero-disk environment variable bridging from EncryptedVault."""

    def __init__(self, vault: Optional[EncryptedVault] = None):
        self.vault = vault or EncryptedVault()

    def get_vault_env(self) -> Dict[str, str]:
        """Loads and decrypts all secrets stored in local EncryptedVault."""
        secrets_dict = {}
        try:
            stored = self.vault.list_secrets()
            for meta in stored:
                val = self.vault.get_secret(meta.key)
                if val is not None:
                    secrets_dict[meta.key] = val
        except Exception:
            pass
        return secrets_dict

    def run_with_vault_env(self, cmd_args: List[str]) -> subprocess.CompletedProcess:
        """Executes a command with decrypted vault secrets securely injected into the environment."""
        merged_env = os.environ.copy()
        merged_env.update(self.get_vault_env())

        return subprocess.run(
            cmd_args,
            env=merged_env,
            capture_output=True,
            text=True,
            check=False
        )


# Global instance
env_sync = EnvSyncBridge()

