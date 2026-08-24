# 🛡️ Saleha AI — Security Model & SAST Guardrails

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

| Rule ID | Severity | Category | Remediation |
|---|---|---|---|
| `SEC001` | HIGH | SQL Injection via string formatting | Use parameterized database queries. |
| `SEC002` | HIGH | Unsafe dynamic execution (`eval`, `exec`, `pickle`) | Use `ast.literal_eval` or JSON parsers. |
| `SEC003` | HIGH | Hardcoded API keys and secrets | Store credentials in `saleha vault`. |
| `SEC004` | HIGH | Insecure subprocess execution (`shell=True`) | Use argument lists without `shell=True`. |
| `SEC005` | LOW | Weak Cryptography (`md5`, `sha1`) | Upgrade to SHA-256 or bcrypt/argon2. |
| `SEC101` | HIGH | Unsafe JS dynamic execution (`eval`/`Function`) | Use `JSON.parse` or safe expression engines. |
| `SEC102` | HIGH | XSS via `dangerouslySetInnerHTML` | Sanitize HTML using DOMPurify. |
| `SEC201` | HIGH | Go SQL injection via `fmt.Sprintf` | Use parameterized `db.Query(..., args)`. |
| `SEC202` | HIGH | Java unsafe deserialization | Use Jackson JSON or Protocol Buffers. |
| `SEC301` | MEDIUM | Unchecked Rust `unsafe { ... }` block | Minimize and isolate unsafe blocks. |

