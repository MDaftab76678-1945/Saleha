"""Unit tests for Saleha Encrypted Secret Vault."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.vault import EncryptedVault


class VaultTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="saleha_vault_test_")
        self.vault_file = os.path.join(self.temp_dir, "test_vault.enc")
        self.vault = EncryptedVault(vault_path=self.vault_file, passphrase="test-secret-passphrase-123")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_and_get_secret(self) -> None:
        ok = self.vault.set_secret("OPENAI_API_KEY", "sk-proj-1234567890abcdef", description="OpenAI API key")
        self.assertTrue(ok)

        val = self.vault.get_secret("OPENAI_API_KEY")
        self.assertEqual(val, "sk-proj-1234567890abcdef")

    def test_has_secret(self) -> None:
        self.assertFalse(self.vault.has_secret("NOT_SET"))
        self.vault.set_secret("EXISTS", "secret_value")
        self.assertTrue(self.vault.has_secret("EXISTS"))

        # Test check_env flag
        os.environ["SALEHA_TEST_TEMP_ENV_VAR"] = "ambient_env_val"
        try:
            self.assertFalse(self.vault.has_secret("SALEHA_TEST_TEMP_ENV_VAR", check_env=False))
            self.assertTrue(self.vault.has_secret("SALEHA_TEST_TEMP_ENV_VAR", check_env=True))
        finally:
            os.environ.pop("SALEHA_TEST_TEMP_ENV_VAR", None)

    def test_get_secret_with_and_without_env_fallback(self) -> None:
        os.environ["SALEHA_TEST_FALLBACK_VAR"] = "ambient_env_123"
        try:
            # Without fallback: returns None because not in vault
            self.assertIsNone(self.vault.get_secret("SALEHA_TEST_FALLBACK_VAR", allow_env_fallback=False))
            # With fallback: returns ambient environment value
            self.assertEqual(self.vault.get_secret("SALEHA_TEST_FALLBACK_VAR", allow_env_fallback=True), "ambient_env_123")
        finally:
            os.environ.pop("SALEHA_TEST_FALLBACK_VAR", None)

    def test_list_secrets_masked_preview(self) -> None:
        self.vault.set_secret("DB_PASSWORD", "super_secret_db_pass_999", description="Production DB")
        secrets_list = self.vault.list_secrets()

        self.assertEqual(len(secrets_list), 1)
        meta = secrets_list[0]
        self.assertEqual(meta.key, "DB_PASSWORD")
        self.assertEqual(meta.description, "Production DB")
        self.assertTrue(meta.preview.startswith("sup..."))
        self.assertTrue(meta.preview.endswith("999"))

    def test_delete_secret(self) -> None:
        self.vault.set_secret("TEMP_KEY", "value_123")
        self.assertIsNotNone(self.vault.get_secret("TEMP_KEY"))

        del_ok = self.vault.delete_secret("TEMP_KEY")
        self.assertTrue(del_ok)
        self.assertIsNone(self.vault.get_secret("TEMP_KEY", allow_env_fallback=False))

    def test_export_to_env(self) -> None:
        self.vault.set_secret("SALEHA_TEST_EXPORT_VAR", "exported_val_777")
        exported = self.vault.export_to_env()

        self.assertIn("SALEHA_TEST_EXPORT_VAR", exported)
        self.assertEqual(os.getenv("SALEHA_TEST_EXPORT_VAR"), "exported_val_777")

    def test_rekey_and_rotation(self) -> None:
        self.vault.set_secret("ROTATION_KEY", "rotation_secret_value_99")
        self.assertEqual(self.vault.get_secret("ROTATION_KEY"), "rotation_secret_value_99")

        # Rotate key
        rotated = self.vault.rekey("new-master-passphrase-456")
        self.assertTrue(rotated)

        # Confirm secret is still accessible with new passphrase
        self.assertEqual(self.vault.get_secret("ROTATION_KEY"), "rotation_secret_value_99")

        # Open with new instance using old passphrase -> fails to decrypt
        vault_old = EncryptedVault(vault_path=self.vault_file, passphrase="test-secret-passphrase-123")
        self.assertIsNone(vault_old.get_secret("ROTATION_KEY", allow_env_fallback=False))

        # Open with new instance using new passphrase -> succeeds
        vault_new = EncryptedVault(vault_path=self.vault_file, passphrase="new-master-passphrase-456")
        self.assertEqual(vault_new.get_secret("ROTATION_KEY"), "rotation_secret_value_99")

    def test_stats(self) -> None:
        self.vault.set_secret("KEY_A", "VAL_A")
        self.vault.set_secret("KEY_B", "VAL_B")

        stats = self.vault.stats()
        self.assertEqual(stats["total_secrets"], 2)
        self.assertTrue(stats["vault_exists"])
        self.assertTrue(stats["salt_exists"])
        self.assertEqual(stats["secret_keys"], ["KEY_A", "KEY_B"])

    def test_clear(self) -> None:
        self.vault.set_secret("TO_CLEAR", "val")
        self.assertEqual(len(self.vault.list_secrets()), 1)
        self.vault.clear()
        self.assertEqual(len(self.vault.list_secrets()), 0)

    def test_tampered_vault_fails_gracefully(self) -> None:
        self.vault.set_secret("SAFE_KEY", "my_value")
        # Tamper the file content
        with open(self.vault_file, "w", encoding="utf-8") as f:
            f.write('{"iv": "abc", "data": "invalid_data", "tag": "bad_tag"}')

        val = self.vault.get_secret("SAFE_KEY", allow_env_fallback=False)
        self.assertIsNone(val)


if __name__ == "__main__":
    unittest.main()

