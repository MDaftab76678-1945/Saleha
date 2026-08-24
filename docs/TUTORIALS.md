# 🚀 Saleha AI — Practical Tutorials & Walkthroughs

Step-by-step guides to master Saleha AI from first run to complex multi-agent enterprise deployments.

---

## Tutorial 1: Your First Self-Healing Code Generation

Run a basic algorithm implementation and watch the self-healing loop:

```powershell
saleha run "Create a function to calculate the Levenshtein distance between two strings with unit tests" -c -x
```

### What Happens:
1. **Planner**: Creates an implementation roadmap.
2. **Coder**: Generates typed Python code.
3. **Auto-Patcher**: Fixes any missing imports.
4. **Tester**: Runs AST validation.
5. **Reviewer**: Evaluates code quality and edge cases.
6. **Verifier**: Executes the code in a sandbox.
7. **Git Auto-Commit**: Creates `feat(core): implement Levenshtein distance`.

---

## Tutorial 2: 5-Agent Collaborative Enterprise Delivery

Generate a complete production package with PRD, Architecture, Code, Security Audit, and Tests:

```powershell
saleha team "Build an in-memory caching system with TTL expiration and LRU eviction" --debate --output-dir ./lru_cache_pkg
```

### Deliverables Generated:
- `PRD.md`: Full product requirements and user stories.
- `DESIGN.md`: Architecture diagrams and interface contracts.
- `solution.py`: Production-grade implementation.
- `SECURITY.md`: AST SAST threat audit report.
- `test_solution.py`: Automated test suite.

---

## Tutorial 3: Using the Encrypted Secret Vault

Protect your API keys and credentials:

```powershell
# 1. Store API key
saleha vault set OLLAMA_HOST "http://127.0.0.1:11434" --desc "Local Ollama host"

# 2. Verify stored secret (masked)
saleha vault list

# 3. Export to environment
saleha vault export
```

