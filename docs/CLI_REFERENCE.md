# 🛠️ Saleha AI — Complete CLI Command Manual

Comprehensive command-line interface reference for all Saleha AI tools, pipelines, and options.

---

## 1. Autonomous Task Execution

### `saleha run`
Executes single-goal self-healing code generation pipeline: Plan ➔ Code ➔ Test ➔ Review ➔ Verify ➔ Commit.

```powershell
saleha run <GOAL> [OPTIONS]
```

**Options:**
- `-m, --model TEXT`: Model name (`auto`, `qwen2.5-coder:1.5b`, `deepseek-coder:6.7b`).
- `-p, --profile TEXT`: Domain agent persona to adopt (e.g. `sde`, `security_engineer`).
- `--max-attempts INT`: Maximum self-healing retry iterations (default: 3).
- `-x, --execute`: Auto-execute verified code immediately upon completion.
- `-c, --commit`: Create atomic conventional git commit upon verified test pass.
- `--json`: Output machine-readable JSON payload.

---

## 2. Multi-Agent Swarm Collaboration

### `saleha team`
Runs 5-Stage collaboration (PM ➔ Architect ➔ SDE ➔ Security ➔ QA).

```powershell
saleha team <GOAL> [OPTIONS]
```

**Options:**
- `--debate`: Enable Architect vs Security Engineer critique & consensus cycle.
- `--output-dir PATH`: Directory path to export complete deliverables (`PRD.md`, `DESIGN.md`, `solution.py`, `SECURITY.md`, `test_solution.py`).
- `--json`: Output full deliverable object in JSON format.

---

## 3. Polyglot Multi-Language Execution

### `saleha exec`
Executes code in isolated sandbox with AST SAST security verification.

```powershell
saleha exec <FILEPATH> [OPTIONS]
```

**Supported Languages:** Python (`.py`), Node.js (`.js`), TypeScript (`.ts`), Go (`.go`), Java (`.java`), Rust (`.rs`).

---

## 4. Headless Browser Automation

### `saleha browser`
Automated Playwright browser navigation, DOM inspection, and screenshot capture.

```powershell
saleha browser <URL> [OPTIONS]
```

**Options:**
- `-s, --selector TEXT`: DOM selectors to verify presence (e.g. `-s "#root" -s "button"`).
- `-p, --screenshot PATH`: File path to save visual PNG screenshot.
- `-t, --timeout INT`: Page load timeout in seconds (default: 10).

---

## 5. Encrypted Secret Vault

### `saleha vault`
PBKDF2-HMAC-SHA256 encrypted credential and secret management.

```powershell
# Set secret
saleha vault set <KEY> <VALUE> [--desc "Description"]

# Get secret
saleha vault get <KEY>

# List all secrets (masked)
saleha vault list

# Delete secret
saleha vault delete <KEY>

# Export secrets to environment
saleha vault export
```

---

## 6. Git-Native Operations

### `saleha git` / `saleha undo`

```powershell
# Install pre-commit AST SAST security gate
saleha git hook install

# Check hook status
saleha git hook status

# View git repository status
saleha git status

# Safe undo/revert of last agent commit
saleha undo
saleha undo --hard
```

---

## 7. Security SAST Scanner

### `saleha sast`
Abstract Syntax Tree static analysis scanner.

```powershell
saleha sast <PATH> [--severity high|medium|low] [--json]
```

---

## 8. Memory & Local Skills

```powershell
# List verified solution memory
saleha memory list

# Semantic vector search
saleha memory search "distributed lock" --semantic

# List 20 Agent profiles
saleha agents

# List local 0ms skills
saleha skills

# Launch dark-mode web studio
saleha serve
```

