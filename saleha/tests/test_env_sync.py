"""Unit tests for Ephemeral Vault Secret & Env Sync Bridge."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock
from saleha.core.env_sync import EnvSyncBridge


class EnvSyncTests(unittest.TestCase):

    def test_run_with_vault_env(self):
        mock_vault = MagicMock()
        mock_meta = MagicMock()
        mock_meta.key = "SALEHA_TEST_INJECTED_SECRET"
        mock_vault.list_secrets.return_value = [mock_meta]
        mock_vault.get_secret.return_value = "secret_val_12345"

        bridge = EnvSyncBridge(vault=mock_vault)
        secrets = bridge.get_vault_env()
        self.assertEqual(secrets.get("SALEHA_TEST_INJECTED_SECRET"), "secret_val_12345")

        res = bridge.run_with_vault_env([sys.executable, "-c", "import os; print(os.getenv('SALEHA_TEST_INJECTED_SECRET', ''))"])
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "secret_val_12345")


if __name__ == "__main__":
    unittest.main()
