"""
Saleha SHA3-Based Symmetric Vault Guard.

Despite the module's prior docstring and class/field names, nothing here
implements CRYSTALS-Kyber, CRYSTALS-Dilithium, or any NIST-standardized
post-quantum algorithm -- there is no lattice-based math, no key
encapsulation mechanism, and no digital signature scheme anywhere in this
file. What actually happens: a random seed hashed with SHA3-512 to produce
two byte strings (labelled "public"/"secret" but with no asymmetric
relationship between them -- knowing one does not let you derive it from
the other via any published KEM), and a SHAKE-256-derived keystream XORed
against the plaintext (a one-time-pad-style stream cipher, not AES-GCM
despite the old return value's name).

This is symmetric-key-strength SHA3/SHAKE-256 hashing, not quantum-safe
asymmetric cryptography. It does not implement Kyber-1024 or Dilithium-5,
is not NIST PQC compliant, and callers must not treat its output as if it
provides the security properties those real algorithms provide (e.g. an
actual KEM's public key cannot be used to derive the same shared secret an
attacker holding only the public key could not also derive; this XOR
stream cipher's "public key" is not used asymmetrically in that sense at
all -- see encrypt_symmetric() below, which takes the caller's own secret
directly rather than pretending to encapsulate one).
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass


@dataclass
class SymmetricKeyMaterial:
    algorithm: str = "SHA3-512-derived (NOT a NIST PQC algorithm)"
    public_key_b64: str = ""
    secret_key_b64: str = ""


@dataclass
class SymmetricEncryptedPayload:
    algorithm: str
    ciphertext_b64: str
    key_hash: str
    nonce_b64: str


class Sha3VaultGuard:
    """
    SHA3/SHAKE-256-based symmetric encryption helper. Not post-quantum
    cryptography -- see module docstring.
    """

    def generate_key_material(self) -> SymmetricKeyMaterial:
        seed = secrets.token_bytes(64)
        pk = hashlib.sha3_512(seed + b"PK").digest()
        sk = hashlib.sha3_512(seed + b"SK").digest()

        return SymmetricKeyMaterial(
            public_key_b64=base64.b64encode(pk).decode("utf-8"),
            secret_key_b64=base64.b64encode(sk).decode("utf-8"),
        )

    def encrypt_symmetric(self, plaintext: str, key_b64: str) -> SymmetricEncryptedPayload:
        """Encrypts with a SHAKE-256-derived keystream XOR, using the
        caller-supplied key directly (there is no separate KEM step)."""
        raw_data = plaintext.encode("utf-8")
        key_bytes = base64.b64decode(key_b64)
        nonce = secrets.token_bytes(16)

        keystream = hashlib.shake_256(key_bytes + nonce).digest(len(raw_data))
        ciphertext = bytes(a ^ b for a, b in zip(raw_data, keystream))

        return SymmetricEncryptedPayload(
            algorithm="SHA3/SHAKE-256 XOR stream cipher (NOT AES-GCM, NOT post-quantum)",
            ciphertext_b64=base64.b64encode(ciphertext).decode("utf-8"),
            key_hash=hashlib.sha256(key_bytes).hexdigest()[:16],
            nonce_b64=base64.b64encode(nonce).decode("utf-8"),
        )

    def decrypt_symmetric(self, payload: SymmetricEncryptedPayload, key_b64: str) -> str:
        ciphertext = base64.b64decode(payload.ciphertext_b64)
        nonce = base64.b64decode(payload.nonce_b64)
        key_bytes = base64.b64decode(key_b64)
        keystream = hashlib.shake_256(key_bytes + nonce).digest(len(ciphertext))
        decrypted = bytes(a ^ b for a, b in zip(ciphertext, keystream))
        return decrypted.decode("utf-8")


sha3_vault_guard = Sha3VaultGuard()

