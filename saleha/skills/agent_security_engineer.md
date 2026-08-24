---
id: "agent_security_engineer"
name: "Principal Application & Cloud Security Engineer"
type: "agent_profile"
version: "2.0.0"
---

# Principal Security Engineer Specification

## 1. Automated Semgrep SAST Rule for Secret Detection
```yaml
rules:
  - id: detect-unencrypted-private-keys
    patterns:
      - pattern-regex: '-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----'
    message: "Hardcoded Private Key detected in source code. Violates Enterprise SecOps Rule #3."
    languages: [generic]
    severity: ERROR
```

