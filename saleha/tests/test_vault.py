"""Unit tests for Saleha Encrypted Secret Vault."""

import os
import shutil
import tempfile
import unittest
from saleha.core.vault import EncryptedVault


class VaultTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="saleha_vault_test_")
        self.vault_file = os.path.join(self.temp_dir, "test_vault.enc")
        self.vault = EncryptedVault(vault_path=self.vault_file, passphrase="test-secret-passphrase-123")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_and_get_secret(self):
        ok = self.vault.set_secret("OPENAI_API_KEY", "sk-proj-1234567890abcdef", description="OpenAI API key")
        self.assertTrue(ok)

        val = self.vault.get_secret("OPENAI_API_KEY")
        self.assertEqual(val, "sk-proj-1234567890abcdef")

    def test_list_secrets_masked_preview(self):
        self.vault.set_secret("DB_PASSWORD", "super_secret_db_pass_999", description="Production DB")
        secrets_list = self.vault.list_secrets()

        self.assertEqual(len(secrets_list), 1)
        meta = secrets_list[0]
        self.assertEqual(meta.key, "DB_PASSWORD")
        self.assertEqual(meta.description, "Production DB")
        self.assertTrue(meta.preview.startswith("sup..."))
        self.assertTrue(meta.preview.endswith("999"))

    def test_delete_secret(self):
        self.vault.set_secret("TEMP_KEY", "value_123")
        self.assertIsNotNone(self.vault.get_secret("TEMP_KEY"))

        del_ok = self.vault.delete_secret("TEMP_KEY")
        self.assertTrue(del_ok)
        self.assertIsNone(self.vault.get_secret("TEMP_KEY"))

    def test_export_to_env(self):
        self.vault.set_secret("SALEHA_TEST_EXPORT_VAR", "exported_val_777")
        exported = self.vault.export_to_env()

        self.assertIn("SALEHA_TEST_EXPORT_VAR", exported)
        self.assertEqual(os.getenv("SALEHA_TEST_EXPORT_VAR"), "exported_val_777")

    def test_tampered_vault_fails_gracefully(self):
        self.vault.set_secret("SAFE_KEY", "my_value")
        # Tamper the file content
        with open(self.vault_file, "w", encoding="utf-8") as f:
            f.write('{"iv": "abc", "data": "invalid_data", "tag": "bad_tag"}')

        val = self.vault.get_secret("SAFE_KEY")
        self.assertIsNone(val)


if __name__ == "__main__":
    unittest.main()

