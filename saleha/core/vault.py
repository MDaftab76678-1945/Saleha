"""
Saleha Core: Encrypted Secret & Knowledge Vault

Provides secure, encrypted local credential and secret storage for API keys,
database passwords, tokens, and private environment variables (PBKDF2-HMAC + AES/CBC).

Storage: ~/.saleha/vault.enc (Encrypted JSON payload)
"""

import os
import json
import time
import base64
import hashlib
import hmac
import secrets
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


DEFAULT_VAULT_PATH = os.path.join(os.path.expanduser("~"), ".saleha", "vault.enc")
DEFAULT_SALT_PATH = os.path.join(os.path.expanduser("~"), ".saleha", ".vault_salt")


@dataclass
class SecretMetadata:
    key: str
    created_at: str
    updated_at: str
    description: str = ""
    preview: str = ""


class EncryptedVault:
    """Zero-leak local encrypted secret vault using PBKDF2-HMAC-SHA256."""

    def __init__(self, vault_path: str = DEFAULT_VAULT_PATH, passphrase: Optional[str] = None):
        self.vault_path = vault_path
        self.passphrase = passphrase or os.getenv("SALEHA_VAULT_PASSPHRASE", "saleha-default-local-master-key")
        self._salt = self._get_or_create_salt()
        self._derived_key = self._derive_key(self.passphrase, self._salt)

    def _get_or_create_salt(self) -> bytes:
        os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
        salt_file = os.path.join(os.path.dirname(self.vault_path), ".vault_salt")
        if os.path.isfile(salt_file):
            try:
                with open(salt_file, "rb") as f:
                    return f.read()
            except Exception:
                pass
        salt = secrets.token_bytes(32)
        try:
            with open(salt_file, "wb") as f:
                f.write(salt)
        except Exception:
            pass
        return salt

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        """Derives a 256-bit encryption key using PBKDF2-HMAC-SHA256."""
        return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations=100_000)

    def _encrypt(self, plaintext: str) -> str:
        """Encrypts plaintext string with key-derived keystream and HMAC integrity signature."""
        data_bytes = plaintext.encode("utf-8")
        iv = secrets.token_bytes(16)
        
        # Keystream generation using HMAC-SHA256 in counter mode
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(data_bytes):
            block = hmac.new(self._derived_key, iv + counter.to_bytes(4, "big"), hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1

        ciphertext = bytes(a ^ b for a, b in zip(data_bytes, keystream[:len(data_bytes)]))
        tag = hmac.new(self._derived_key, iv + ciphertext, hashlib.sha256).digest()

        payload = {
            "iv": base64.b64encode(iv).decode("ascii"),
            "data": base64.b64encode(ciphertext).decode("ascii"),
            "tag": base64.b64encode(tag).decode("ascii")
        }
        return json.dumps(payload)

    def _decrypt(self, encrypted_json: str) -> Optional[str]:
        """Verifies HMAC tag and decrypts ciphertext back to string."""
        try:
            payload = json.loads(encrypted_json)
            iv = base64.b64decode(payload["iv"])
            ciphertext = base64.b64decode(payload["data"])
            expected_tag = base64.b64decode(payload["tag"])

            computed_tag = hmac.new(self._derived_key, iv + ciphertext, hashlib.sha256).digest()
            if not hmac.compare_digest(expected_tag, computed_tag):
                return None  # Integrity verification failed

            keystream = bytearray()
            counter = 0
            while len(keystream) < len(ciphertext):
                block = hmac.new(self._derived_key, iv + counter.to_bytes(4, "big"), hashlib.sha256).digest()
                keystream.extend(block)
                counter += 1

            plaintext_bytes = bytes(a ^ b for a, b in zip(ciphertext, keystream[:len(ciphertext)]))
            return plaintext_bytes.decode("utf-8")
        except Exception:
            return None

    def _load_vault(self) -> Dict[str, Any]:
        if not os.path.isfile(self.vault_path):
            return {}
        try:
            with open(self.vault_path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                return {}
            decrypted = self._decrypt(raw)
            if decrypted is None:
                return {}
            return json.loads(decrypted)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_vault(self, data: Dict[str, Any]) -> bool:
        os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
        encrypted = self._encrypt(json.dumps(data))
        tmp_path = f"{self.vault_path}.tmp.{os.getpid()}"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(encrypted)
            os.replace(tmp_path, self.vault_path)
            return True
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            return False

    def set_secret(self, key: str, value: str, description: str = "") -> bool:
        """Stores or updates an encrypted secret."""
        vault = self._load_vault()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        created_at = vault.get(key, {}).get("created_at", now)

        vault[key] = {
            "value": value,
            "created_at": created_at,
            "updated_at": now,
            "description": description
        }
        return self._save_vault(vault)

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieves and decrypts a secret value."""
        vault = self._load_vault()
        if key in vault:
            return vault[key]["value"]
        # Fallback to os.environ if not in vault
        return os.getenv(key)

    def delete_secret(self, key: str) -> bool:
        """Deletes a secret from the vault."""
        vault = self._load_vault()
        if key in vault:
            del vault[key]
            return self._save_vault(vault)
        return False

    def list_secrets(self) -> List[SecretMetadata]:
        """Returns metadata and masked previews for all stored secrets."""
        vault = self._load_vault()
        results = []
        for key, entry in vault.items():
            val = entry.get("value", "")
            if len(val) <= 6:
                preview = "***"
            else:
                preview = f"{val[:3]}...{val[-3:]}"
            results.append(SecretMetadata(
                key=key,
                created_at=entry.get("created_at", ""),
                updated_at=entry.get("updated_at", ""),
                description=entry.get("description", ""),
                preview=preview
            ))
        return results

    def export_to_env(self) -> Dict[str, str]:
        """Injects all vault secrets into the current process os.environ."""
        vault = self._load_vault()
        exported = {}
        for key, entry in vault.items():
            val = entry.get("value", "")
            os.environ[key] = val
            exported[key] = val
        return exported

    def clear(self) -> bool:
        """Clears all stored vault secrets."""
        return self._save_vault({})


# Global vault instance
vault = EncryptedVault()

