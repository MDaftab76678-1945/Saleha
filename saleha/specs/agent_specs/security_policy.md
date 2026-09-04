---
id: "doc_security_policy"
title: "Enterprise Information Security Policy & Governance Standard"
version: "3.0.0"
---

# Enterprise Information Security Policy

## 1. Mandatory Cryptographic Standards
* **Symmetric Encryption:** AES-GCM with 256-bit keys.
* **Asymmetric Signatures:** Ed25519 or ECDSA with curve secp256r1.
* **Key Derivation Function (KDF):** Argon2id ($m=65536, t=3, p=4$) or PBKDF2 ($N \ge 600,000$).
* **Transport Security:** TLS 1.3 only; TLS 1.0, 1.1, and 1.2 are blocked at edge gateways.
