# 🛡️ Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.6.x   | :white_check_mark: |
| 2.5.x   | :white_check_mark: |
| 2.0.x   | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

We take the security of Saleha AI extremely seriously. If you discover a vulnerability or security issue:

1. **Do not disclose publicly** in GitHub issues.
2. Email the maintainer directly at `alamaftab76678@gmail.com` with detailed steps to reproduce.
3. Include code snippets, proof-of-concept, and your environment setup.
4. We will respond within 48 hours and work with you to release a patch.

## Built-in SAST & Constitutional Guardrails

Saleha incorporates multi-tier security engines:
- **Constitutional AI Guard** (`saleha constitutional-check`): Rule-based runtime enforcement against unauthorized socket exfiltration and destructive system commands.
- **Hardware RTL SAST Scanner** (`saleha scan-sec`): AST-level scanning for Software and Verilog/SystemVerilog hardware designs.
- **Isolated Process Sandbox** (`saleha/core/sandbox_runner.py`): Zero unauthenticated disk/network escape policy.
- **Merkle Provenance Audit** (`saleha merkle-audit`): SHA-256 cryptographic immutable patch trail.
