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

## Built-in security tooling

Saleha includes a few security-relevant modules, described plainly (see ARCHITECTURE.md for details):

- **Rule-based code audit** (`saleha constitutional-check <path>`, `saleha/core/constitutional_guard.py`): static checks against a fixed set of rules (e.g. flags obviously destructive or exfiltration-shaped patterns). It is a heuristic linter, not a runtime sandbox enforcement mechanism.
- **Static security scanner** (`saleha sast <path>`, `saleha/core/security_scanner.py`): AST-level checks for common Python issues (`shell=True`, bare `except`, hardcoded secrets, string-built SQL), with limited Verilog/SystemVerilog pattern checks.
- **Sandboxed execution** (`saleha sandbox <file>`, `saleha/core/sandbox_runner.py` / `docker_sandbox.py`): runs generated or untrusted code in a resource-limited subprocess or Docker container rather than directly on the host. This reduces blast radius; it is not a formally verified isolation guarantee.
- **Hash-chained audit log** (`saleha merkle-audit`, `saleha/core/merkle_provenance.py`): verifies that the recorded action log has not been tampered with, using a SHA-256 hash chain.

None of the above is a substitute for an independent security review of your own deployment.
