# 🛠️ Saleha CLI Reference

> ⚠️ Ye file **auto-generated** hai -- `python scripts/gen_cli_docs.py`
> (Generated against Saleha CLI, 63 top-level commands)

## Commands

### All Commands

| Command | Description | Options |
|---|---|---|
| `saleha agent` | Autonomous agent that thinks, uses tools, and investigates a repo. | `<GOAL>` `--dir `ROOT_DIR`` `--model/-m `MODEL`` `--max-steps `MAX_STEPS`` `--write` `--json` |
| `saleha agents` | Show dynamic agent profiles loaded from saleha/skills/. | `--json` |
| `saleha ask` | Ask Saleha a normal question without starting the interactive shell. | `<QUESTION>` `--model/-m `MODEL`` `--json` |
| `saleha audit` | Show recent code-execution audit records. | `--limit/-n `LIMIT`` `--blocked-only` `--json` |
| `saleha autodoc` | Generate Markdown API docs and Mermaid architecture diagrams from AST. | `<PATH>` `--output-dir/-o `OUTPUT_DIR`` `--json` |
| `saleha benchmark` | Benchmark local Ollama models on HumanEval-style coding challenges. | `--model/-m `MODEL`` `--limit/-l `LIMIT`` `--dry-run` `--json` |
| `saleha browser` | Automated Headless Browser Testing & Verification (Playwright). | `<URL>` `--selector/-s `SELECTOR`` `--screenshot/-p `SCREENSHOT`` `--timeout/-t `TIMEOUT`` `--json` |
| `saleha callers` | Find all code callers referencing a specific function, class, or method. | `<SYMBOL>` `--json` |
| `saleha canvas` | Alias for 'saleha tui'. | - |
| `saleha chat` | Start an interactive pair-programming shell with Saleha agents. | `--profile/-p `PROFILE`` `--model/-m `MODEL`` |
| `saleha code` | Generate code for a specific task | `<TASK>` `--model/-m `MODEL`` `--json` `--output `OUTPUT`` |
| `saleha dag` | Execute a complex engineering goal using a parallel Directed Acyclic Graph (DAG) of agents. | `<GOAL>` `--parallel` `--workers/-w `WORKERS`` `--model/-m `MODEL`` `--json` |
| `saleha dashboard` | Render the Saleha multi-agent operations dashboard. | `--live` `--refresh `REFRESH`` |
| `saleha debug` | Diagnose an error and generate corrected code. | `<CODE_FILE>` `<ERROR_LOG>` `--model/-m `MODEL`` `--save` `--error-file `ERROR_FILE`` `--output `OUTPUT`` `--json` |
| `saleha debug-repl` | Start an interactive stateful Python AI REPL & live variable debugger. | - |
| `saleha deploy` | Generate production-ready Dockerfile, Compose, and Kubernetes manifests. | `--target/-t `TARGET`` `--output-dir/-o `OUTPUT_DIR`` `--name/-n `NAME`` `--port/-p `PORT`` `--json` |
| `saleha doc` | Look up verified API signatures from local offline documentation cache. | `<PACKAGE>` `<SYMBOL>` `--json` |
| `saleha doctor` | Saleha ke common problems ko check karta hai -- jaise wo saari cheezein | `--json` |
| `saleha edit` | Plan (and optionally apply) multi-file edits across an existing repo. | `<GOAL>` `--dir `ROOT_DIR`` `--model/-m `MODEL`` `--apply` `--json` |
| `saleha exec` | Execute code in multi-language sandbox with pre-execution AST SAST security gates. | `<FILEPATH>` `--lang/-l `LANG`` `--timeout/-t `TIMEOUT`` `--json` |
| `saleha fuzz` | Execute automated security mutation fuzzing against code functions. | `<FUNC_NAME>` `--mutations/-m `MUTATIONS`` `--json` |
| `saleha graph` | Build and inspect cross-file AST symbol call dependency graph. | `<PATH>` `--json` |
| `saleha history` | Show recent task history (saved in ~/.saleha/history.jsonl) | `--limit/-n `LIMIT`` `--failed-only` `--json` |
| `saleha interactive` | Start interactive Saleha shell | `--model/-m `MODEL`` |
| `saleha loadtest` | Execute high-concurrency API load testing and percentile benchmarks. | `<URL>` `--concurrency/-c `CONCURRENCY`` `--requests/-r `REQUESTS`` `--dry-run` `--json` |
| `saleha metrics` | Show run success-rate, avg attempts, per-model stats & recent events. | `--tail/-n `TAIL`` `--json` |
| `saleha models` | Show all available models and their stats | `--json` |
| `saleha plan` | Generate task plan only (no code generation) | `<GOAL>` `--model/-m `MODEL`` `--json` |
| `saleha plugins` | List loaded dynamic plugins and lifecycle event hooks. | `--json` |
| `saleha pr` | Autonomously generate git branch, conventional commit, test evidence, and PULL_REQUEST.md. | `<GOAL>` `--branch/-b `BRANCH`` `--output-dir/-o `OUTPUT_DIR`` `--debate` `--push` `--open-remote` `--base `BASE`` `--model/-m `MODEL`` `--json` |
| `saleha pr-review` | Analyze Git PR diff, run SAST security scan, and generate review comments. | `<BASE_BRANCH>` `--output-file/-o `OUTPUT_FILE`` `--json` |
| `saleha project` | Build a multi-file project (breaks goal into files, generates each) | `<GOAL>` `--model/-m `MODEL`` `--json` `--output-dir `OUTPUT_DIR`` |
| `saleha rag` | Natural language architectural Q&A fused with AST Dependency Graph. | `<QUESTION>` `--path/-p `PATH`` `--json` |
| `saleha refactor` | Refactor a Python file surgically using AST analysis and unified diff patching. | `<TARGET_FILE>` `<INSTRUCTION>` `--model/-m `MODEL`` `--diff-only` `--json` |
| `saleha repl` | Alias for 'saleha chat'. | `--profile/-p `PROFILE`` `--model/-m `MODEL`` |
| `saleha run` | Full self-healing pipeline: Plan -> Code -> Test -> Fix -> Execute | `<GOAL>` `--model/-m `MODEL`` `--profile/-p `PROFILE`` `--max-attempts `MAX_ATTEMPTS`` `--verbose/-v` `--execute/-x` `--commit/-c` `--context-dir/-cd `CONTEXT_DIR`` `--tests/-t` `--resume/-r` `--stream` `--json` |
| `saleha sandbox` | Execute a script inside an isolated ephemeral virtual environment or Docker sandbox. | `<TARGET_FILE>` `--deps/-d `DEPS`` `--timeout/-t `TIMEOUT`` `--docker` `--lang `LANG`` `--json` |
| `saleha sast` | Deep AST Security SAST scanner for detecting SQL injection, hardcoded secrets, and unsafe execution. | `<PATH>` `--severity/-s `SEVERITY`` `--json` |
| `saleha scan` | Scan and index codebase AST symbols (classes, methods, functions, imports). | `<DIRECTORY>` `--json` |
| `saleha serve` | Launch the interactive Saleha Web Studio & REST API Server. | `--host `HOST`` `--port `PORT`` `--open` |
| `saleha sidecar` | Launch the floating desktop AI companion daemon on localhost:7890. | `--host `HOST`` `--port `PORT`` `--open` |
| `saleha skills` | Show skills registered in Saleha's local skill registry. | `--json` |
| `saleha stats` | Show persistent model performance stats (saved in ~/.saleha/stats.json) | `--task-type/-t `TASK_TYPE`` `--json` |
| `saleha status` | Show Saleha system status | - |
| `saleha stream` | Stream generated tokens in real-time with typewriter syntax highlighting. | `<PROMPT>` `--model/-m `MODEL`` |
| `saleha swe-bench` | Run SWE-Bench verified evaluation harness on repository-level bug fixing instances. | `--limit/-l `LIMIT`` `--dry-run` `--json` |
| `saleha team` | Run multi-agent collaborative swarm pipeline: | `<GOAL>` `--model/-m `MODEL`` `--output-dir/-o `OUTPUT_DIR`` `--debate` `--max-attempts `MAX_ATTEMPTS`` `--json` |
| `saleha test` | Test code for syntax and security | `<CODE_FILE>` `--json` |
| `saleha tools` | List all available dynamic tools and their JSON schemas. | `--json` |
| `saleha tui` | Launch full-screen interactive Terminal TUI Canvas IDE. | - |
| `saleha ui` | Alias for 'saleha dashboard'. | `--live` `--refresh `REFRESH`` |
| `saleha undo` | Safely undo/rollback the last Saleha Git commit (Aider-style). | `--hard` `--json` |
| `saleha vision` | Synthesize UI code from specs OR from a real screenshot via local vision models. | `<SPEC>` `--framework/-f `FRAMEWORK`` `--name/-n `NAME`` `--image/-i `IMAGE`` `--output-file/-o `OUTPUT_FILE`` `--json` |
| `saleha voice` | Hands-free voice prompt listener and autonomous code synthesizer. | `<PROMPT>` `--model/-m `MODEL`` |

#### `saleha ci` group

| Sub-command | Description | Options |
|---|---|---|
| `saleha ci review` | Run autonomous AST SAST security audit and code quality review. | `<TARGET_DIR>` `--pr `PR_NUMBER`` `--output/-o `OUTPUT`` `--json` |

#### `saleha db` group

| Sub-command | Description | Options |
|---|---|---|
| `saleha db optimize` | Analyze SQL DDL or models for missing indexes and generate UP/DOWN migrations. | `<SCHEMA_OR_FILE>` `--json` |

#### `saleha git` group

| Sub-command | Description | Options |
|---|---|---|
| `saleha git hook` | Manage Git pre-commit AST SAST security gates. | `<ACTION>` `--json` |
| `saleha git status` | View current Git repository status and branch. | `--json` |

#### `saleha harness` group

| Sub-command | Description | Options |
|---|---|---|
| `saleha harness leaderboard` | Display persistent model ranking leaderboard. | - |
| `saleha harness list` | List available benchmark datasets in the harness catalog. | `--json` |
| `saleha harness run` | Run comprehensive multi-domain model evaluation and compute Pass@k metrics. | `--benchmark/-b `BENCHMARK`` `--model/-m `MODEL`` `--limit/-l `LIMIT`` `--workers/-w `WORKERS`` `--output-file/-o `OUTPUT_FILE`` `--dry-run` `--json` |

#### `saleha mcp` group

| Sub-command | Description | Options |
|---|---|---|
| `saleha mcp serve` | Start standard Model Context Protocol (MCP) server for Claude Desktop, Cursor, etc. | `--stdio` |
| `saleha mcp tools` | List all tools exposed by the Saleha MCP Server. | `--json` |

#### `saleha memory` group

| Sub-command | Description | Options |
|---|---|---|
| `saleha memory clear` | Clear all verified solutions from persistent memory. | `--yes/-y` |
| `saleha memory list` | List verified solutions stored in persistent memory. | `--limit/-n `LIMIT`` `--json` |
| `saleha memory search` | Search solutions in memory by keyword, tag, or vector semantic similarity. | `<QUERY>` `--semantic` `--json` |
| `saleha memory stats` | Show memory store statistics. | `--json` |

#### `saleha sre` group

| Sub-command | Description | Options |
|---|---|---|
| `saleha sre analyze` | Analyze production stacktrace and synthesize emergency hotfix patch. | `<LOG_OR_FILE>` `--json` |

#### `saleha vault` group

| Sub-command | Description | Options |
|---|---|---|
| `saleha vault delete` | Delete a secret from the vault. | `<KEY>` |
| `saleha vault export` | Inject all vault secrets into the current environment session. | - |
| `saleha vault get` | Retrieve and decrypt a secret value from the vault. | `<KEY>` |
| `saleha vault list` | List all stored secrets with masked previews and timestamps. | `--json` |
| `saleha vault set` | Store or update an encrypted secret in the vault. | `<KEY>` `<VALUE>` `--desc `DESC`` |

#### `saleha workspace` group

| Sub-command | Description | Options |
|---|---|---|
| `saleha workspace status` | Audit branch status and uncommitted changes across all workspace repos. | `--path/-p `PATH`` `--json` |

