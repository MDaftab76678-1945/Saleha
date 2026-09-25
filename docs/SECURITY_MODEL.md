# Saleha AI — Security Model & SAST Guardrails

<!-- saleha:generated:doc-version -->
Document version 1.0.1 -- describes Saleha 2.6.0 -- updated 2026-09-25
<!-- /saleha:generated:doc-version -->

Saleha AI is designed around a zero-trust, local-first security architecture to prevent credential leaks, code injection, and arbitrary remote code execution.

---

## 1. Security Architecture Layers

```
┌────────────────────────────────────────────────────────┐
│ 1. Git Pre-Commit Security Hook (.git/hooks/pre-commit) │
├────────────────────────────────────────────────────────┤
│ 2. Deep AST SAST Scanner (SEC001 - SEC301)             │
├────────────────────────────────────────────────────────┤
│ 3. Isolated Sandbox Directory Execution                │
├────────────────────────────────────────────────────────┤
│ 4. Encrypted Secret Vault (PBKDF2-HMAC-SHA256)         │
├────────────────────────────────────────────────────────┤
│ 5. Audit Logging (~/.saleha/audit_log.jsonl)           │
└────────────────────────────────────────────────────────┘
```

---

## 2. Rule Catalog

Generated from `RULE_CATALOG` in `saleha/core/verification/security_scanner.py`
by `saleha governance docs --apply`; the `GOV-SAST-CATALOG` and
`GOV-DOCS-RULES` controls fail if the code, the catalog and this table
disagree. Edit the catalog, not the table.

<!-- saleha:generated:security-rules -->
| Rule ID | Severity | Language | Detects | Remediation |
|---|---|---|---|---|
| `SEC001` | HIGH | Python | SQL built with f-strings, `+` or `%` inside execute() | Use parameterized queries. |
| `SEC002` | HIGH | Python | Dynamic execution (`eval`, `exec`) or unsafe deserialization (`pickle`, `marshal`, `yaml.unsafe_load`) | Use `ast.literal_eval`, JSON, or safe loaders. |
| `SEC003` | HIGH | Python, JS/TS, Rust | Hardcoded credential or secret | Read secrets from the environment or `saleha vault`. |
| `SEC004` | MEDIUM | Python | `subprocess` call with `shell=True` | Pass an argument list with `shell=False`. |
| `SEC005` | LOW | Python | Weak hash (`md5`, `sha1`) | Use SHA-256, bcrypt or argon2. |
| `SEC101` | HIGH | JS/TS | Dynamic execution (`eval`, `new Function`) | Use `JSON.parse` or a safe expression parser. |
| `SEC102` | HIGH | JS/TS | Unescaped HTML (`dangerouslySetInnerHTML`, `document.write`) | Sanitize with DOMPurify or render text. |
| `SEC103` | MEDIUM | JS/TS | `child_process.exec` / `execSync` | Use `execFile` or `spawn` with an argument array. |
| `SEC201` | HIGH | Go | SQL built with `fmt.Sprintf` or `+` in `db.Query/Exec` | Use placeholder arguments. |
| `SEC202` | HIGH | Java | `ObjectInputStream` / `readObject` deserialization | Use JSON or Protocol Buffers. |
| `SEC301` | MEDIUM | Rust | `unsafe { ... }` block | Keep unsafe blocks minimal behind safe abstractions. |
<!-- /saleha:generated:security-rules -->

## 3. Governance Controls

`saleha governance check` runs these against the repository itself. A
control that cannot run reports `NOT_CHECKED`, never `PASS`. Ratcheted
controls fail when their count rises above the recorded baseline, and the
tooling only ever lowers a baseline. See [GOVERNANCE.md](GOVERNANCE.md).

<!-- saleha:generated:governance-controls -->
| Control | What it checks | Ratchet baseline |
|---|---|---|
| `GOV-SAST-CATALOG` | Parses security_scanner.py; every emitted rule_id/severity must equal RULE_CATALOG. | - |
| `GOV-SAST-TESTS` | Each RULE_CATALOG id must be named in a saleha/tests file (ratchet). | `untested_scanner_rules` <= 0 |
| `GOV-DOCS-RULES` | The generated rule table must equal a fresh render of RULE_CATALOG. | - |
| `GOV-LOCAL-ONLY` | Runs each cloud provider with local-only set and intercepts network/CLI calls. | - |
| `GOV-COMMIT-GATE` | Checks .git/hooks/pre-commit exists and invokes preflight_lint.py. | - |
| `GOV-SUBPROCESS-TIMEOUT` | Counts run/call/check_call/check_output without timeout= (ratchet). | `subprocess_without_timeout` <= 24 |
| `GOV-SUBPROCESS-ENCODING` | Counts text=True calls without encoding= (ratchet). | `subprocess_text_without_encoding` <= 47 |
| `GOV-SAST-SELF` | Runs the SAST scanner over saleha/ excluding tests (ratchet). | `high_sast_findings` <= 12 |
| `GOV-DOCS-STALE` | Checks backticked `saleha ...` commands and repo paths in docs (ratchet). | `stale_doc_claims` <= 0 |
| `GOV-VERSION` | pyproject.toml and saleha/__init__.py must declare the same version. | - |
<!-- /saleha:generated:governance-controls -->