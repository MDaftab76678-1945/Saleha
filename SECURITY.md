# 🛡️ Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :x:                |

## Reporting a Vulnerability

We take the security of Saleha AI extremely seriously. If you discover a vulnerability or security issue:

1. **Do not disclose publicly** in GitHub issues.
2. Email the maintainer directly at `security@saleha.ai` with detailed steps to reproduce.
3. Include code snippets, proof-of-concept, and your environment setup.
4. We will respond within 48 hours and work with you to release a patch.

## Built-in SAST Guardrails

Saleha incorporates static AST analysis (`saleha sast`) to prevent:
- Dangerous command execution (`eval`, `exec`, `shell=True`)
- SQL Injection in raw query strings
- Hardcoded credentials and secret tokens
- Insecure deserialization (`pickle.loads`, `ObjectInputStream`)

