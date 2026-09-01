# Changelog

All notable changes to Saleha AI Framework are documented here.

## [2.6.0] - 2026-09-02 (Sovereign Intelligence & Marketplace Release)

### 🌟 34 Sovereign Flagship Systems
- **Swarm PBFT Consensus Protocol** (`saleha consensus`): Multi-agent Byzantine Fault Tolerance ($2f+1$ Quorum).
- **Constitutional AI Safety Guard** (`saleha constitutional-check`): Rule-based invariant enforcement.
- **Formal Logic Lean 4 Prover** (`saleha formal-verify`): Mathematical contract and proof synthesizer.
- **Pearl Causal World Model** (`saleha causal-eval`): Counterfactual $L_1 \to L_3$ intervention analysis.
- **Gödel Self-Proving Utility** (`saleha godel-utility`): Proof-bounded recursive self-improvement.
- **Emergent Swarm & Gini Collusion Monitor** (`saleha emergence-check`): Deadlock and communication divergence detection.
- **Mechanistic Interpretability Engine** (`saleha explain-code`): Syntactic circuit and attribution discovery.
- **Merkle Tree Audit Ledger** (`saleha merkle-audit`): SHA-256 immutable cryptographic lineage trail.
- **Quadratic Voting & VCG Mechanism** (`saleha quadratic-vote`): Truthful resource allocation in swarms.
- **Autonomous Headless Browser UI Inspector** (`saleha test-ui`): DOM inspection, console error detection, viewport health.
- **Isolated Process & Container Sandbox** (`saleha sandbox-run`): Sanitized containment environment.
- **SWE-Bench Benchmark Runner** (`saleha swebench-eval`): Real-world SWE-Bench Lite evaluation scorecard.
- **Full-Screen Terminal TUI Workspace** (`saleha tui`): Aider-style split-screen interactive terminal.
- **SWE-Bench Public Leaderboard Generator** (`saleha leaderboard`): Comparative HTML/Markdown matrix generator.
- **Saleha Hub Community Plugin Loader** (`saleha hub`): Dynamic plugin & skill registry.
- **VS Code Extension Packager** (`editors/vscode/build_extension.py`): 1-Click `.vsix` packaging for VS Code & Open-VSX marketplaces.
- **100% Test Suite Pass**: 783/783 tests passed (0 failures).

## [1.5.0] - 2026-09-01

### 🚀 Features & Enhancements
- Implement 4 Expansion Pillars - Visual Browser UI Tester (saleha test --browser), JSON-RPC LSP Daemon (saleha lsp --stdio), Multi-Repo Swarm (saleha multi-repo), and Live Graph Visualizer (saleha graph)
- Implement 5 Major Frontiers - Multi-File Refactorer (saleha refactor), Dynamic Skill Synthesizer (saleha learn), Token Analytics (saleha budget), Architecture Debater (saleha debate), and Polyglot AST Engine
- Implement 4 Next-Gen Pillars - Self-Healing Loop (saleha fix), Hybrid BM25+Vector Search (saleha search), Ensemble Reviewer (saleha review --ensemble), and Real-Time HUD (saleha hud)
- Implement 4 Final Frontiers - Compiler LSP, CloudDeployer, DBOptimizer audit, and Standalone Packager
- Add 5 Next-Gen Pillars - RepoWatcher, InteractiveDiff, SWE-bench suite, MemoryCompactor & Supercharged REPL
- Add saleha doctor diagnostic suite with auto-repair and JSON output
- Add /api/agent/run and /api/diff/patch REST endpoints to Web Studio gateway
- Add saleha agent autonomous ReAct CLI entrypoint with surgical AST tools
- Speculative task tier classifier & fast model cascading in SmartRouter
- Git Worktree isolated agent execution & universal installer enhancements
- DeepSeek-R1 reasoning parser, agentic surgical tools & downstream graph intelligence
- Aider-style search-replace, fuzzy line matching & surgical patching
- collaborative rooms + hardware profiler (v1.6)
- enrich all 20 agent profiles + quality gate + allowed_tools wiring
- profile llm_routing is now real (role complexity floors + temperature)
- real voice STT/TTS (faster-whisper + pyttsx3) + community files
- tree-sitter context ranking (codeintel extra) + auto-generated CLI docs
- Saleha v1.2.0 - autonomous multi-agent AI engineering platform

### 🩹 Bug Fixes & Resilience
- Implement 5 enterprise resilience fixes - atomic writes, RLock thread-safety, atexit worktree cleanup, timeout deadline, GraphRAG path normalization
- Fix Tuple import in codebase_indexer and modernize python -m pytest in CI workflow
- Add Any and Tuple imports to smart_router.py for Python 3.11/3.12 compatibility
- Fix invalid GitHub Action versions (v5->v4, v6->v5, v8->v7) and use pytest runner
- pytest collection, dependency sync, polyglot fallback & repo URL updates
- eliminate last SEC101 self-scan findings in extension.js
- resolve SAST findings flagged by our own review bot (self-dogfood)
- cross-drive relpath crash + docker cmd path normalization (CI)
- strip UTF-8 BOM from pyproject/setup/package.json (broke pip install in CI)

# 📜 Changelog

All notable changes to **Saleha AI** are documented in this file.

---

## [1.6.0] - 2026-08-25 (Collab & Telemetry Release)

### 👥 Collaborative Editing Rooms (real implementation)
- **`saleha/core/collab.py`**: versioned multi-user document rooms with optimistic concurrency (stale base_version -> 409 conflict), participant presence + cursor tracking, inactivity TTL, room caps.
- **Web API** (token-gated): `/api/collab/create | join | update | poll | state | list | leave` — polling-based sync jo LAN ke doosre browsers/machines pe bhi kaam karta hai.

### 🖥️ Hardware Profiler (deep telemetry)
- **`saleha/core/hardware_profiler.py`**: CPU (per-core, freq), RAM/swap, disk & net throughput deltas, top-processes (Saleha self-highlighted), optional nvidia-smi GPU probe.
- Rolling history ring-buffer + windowed report aggregation.
- **Naya command `saleha profile [--watch N] [--json]`** — live Rich table output.

---

## [1.5.0] - 2026-08-25 (Profile Quality Release)

### 🎭 Agent Profiles: 19/20 THIN -> 20/20 RICH
- Har profile ab **role-specific goals (>=3), constraints (>=2), allowed_tools, llm_routing.temperature** carry karti hai -- pehle average persona ~80 words with zero structure tha.
- **Quality gate tests** (`test_profile_quality_gate.py`): richness bar enforce hota hai -- koi profile wapas thin ho to CI fail.
- `allowed_tools` vocabulary normalized (run_code/read_file/... known names).

### 🔧 allowed_tools Ab REAL
- **AgentLoop `allowed_tools` filter**: profile ke declared tools se agent ka toolset restrict hota hai (`saleha agent` + swarm agents). Khali intersection = graceful full-set fallback.

---

## [1.4.0] - 2026-08-25 (Voice & Community Release)

### 🎙️ Real Voice (STT + TTS)
- **`saleha/core/speech.py`**: faster-whisper local transcription (CPU int8, model cache, language detect) + pyttsx3 offline TTS.
- **CLI**: `saleha voice --audio note.wav [--speak]` — audio → text → autonomous pipeline → spoken summary. Whisper model choice: `--whisper-model tiny|base|small|medium`.
- Optional `[voice]` extra; missing deps = clear install guidance (koi silent stub nahi).

### 🤝 Community
- GitHub **issue templates** (bug report with env checklist + feature request format).
- **CONTRIBUTING.md rewritten**: setup, extras policy, sandbox/security rules for PRs, project layout map, cross-platform path guidelines.

---

## [1.3.0] - 2026-08-25 (Tree-sitter Context Ranking)

### 🗺️ Aider-level Context Engine (optional `[codeintel]` extra)
- **`saleha/core/tree_context_ranker.py`**: tree-sitter based multi-language symbol extraction -- JS/TS ab bhi real AST se (regex guess nahi), line numbers ke saath.
- **Symbol-popularity hub boost**: jo files shared symbols define karti hain jinhe doosri files reference karti hain, wo up-rank hoti hain (Aider repo-map ka core signal).
- **Zero-dependency graceful fallback**: grammars na hon to packer apne existing keyword/AST path pe chalta hai; CI core install untouched.
- Install: `pip install saleha[codeintel]`

### 📚 Docs
- **Auto-generated `docs/CLI_REFERENCE.md`** (`scripts/gen_cli_docs.py`) -- Click introspection se, ab CLI docs kabhi stale nahi honge.
- 🏷️ GitHub Release v1.2.0 published.

### Fixed
- UTF-8 BOM strip (pyproject/setup/package.json) jo fresh CI installs todta tha.

---

## [1.2.0] - 2026-08-25 (Streaming & Observability Release)

### ⚡ Token Accounting (end-to-end)
- `ProviderResponse.tokens_used` -- Ollama `eval_count` capture (streaming + non-streaming dono).
- `BaseAgent.total_tokens_used` session-lifetime accumulation; metrics ab per-run token usage record karta hai.

### 📡 `saleha run --stream`
- Coder tokens terminal pe live stream hote hain (spinner auto-disable hota hai streaming mode mein). `on_token` callback orchestrator tak wired.

### 🏃 SWE-bench Lite Prediction Generator
- **`saleha/core/swe_bench_runner.py`**: instance -> prompt building, orchestrator run, **official predictions.jsonl format** writer (instance_id/model_name_or_path/model_patch).
- Real-diff mode jab repo checkout diya ho; synthetic new-file diff warna (documented limitation -- official score official harness se hi aayega).

### 📝 README Overhaul
- Complete rewrite: capability matrix, naye commands (agent/edit/metrics/vision), env-var reference table, updated architecture diagram, sandbox modes, resume workflow.

---

## [1.1.0] - 2026-08-25 (Agentic Loop Release)

### 🤖 A: Agentic Tool-Use Loop (ReAct) -- keystone primitive
- **`saleha/core/agentic_loop.py`**: model KHUD decide karta hai agla kadam -- think -> tool call -> observation -> repeat -> finish. Fixed-stage pipeline se autonomous investigation tak.
- Repo-sandboxed tools: `list_dir`, `read_file`, `search_repo`, `run_code` (Docker policy applies), `write_file` (opt-in + approval-gated).
- Path-traversal blocking, observation truncation, max-steps guard, `on_event` per-step streaming.
- **Naya command**: `saleha agent "find endpoints missing auth" --dir ./src [--write] [--max-steps 20]`

### 🔌 B: Plugin Hooks Wired (pehli baar real)
- Orchestrator ab `on_task_start` / `on_code_generated` / `on_test_complete` events fire karta hai -- plugin ecosystem functional hai, sirf loader nahi.

### 📄 C: Unified Diff Previews
- `saleha edit` dry-run ab existing files ke liye **real unified diffs** dikhata hai (SmartPatcher reuse) -- plan table + syntax-highlighted diffs.

---

## [1.0.0] - 2026-08-25 (Real Vision Release)

### 👁️ Real Multimodal Vision (aakhri genuine stub closed)
- **`saleha/core/vision_backend.py`**: local Ollama vision models (llava, qwen2-vl, llama3.2-vision, minicpm-v, moondream...) se **screenshot -> working UI code**. Runtime model probing (`find_vision_model`) SmartRouter probe reuse karta hai.
- `VisionCoder.synthesize_ui(image_source=...)`: file path / raw base64 / data-URL support, 8MB cap, fenced-code extraction.
- **Graceful degradation**: vision model na ho ya call fail -> text-LLM fallback -> template. `used_vision` / `model_used` / `source_note` fields se caller ko full transparency.
- **CLI**: `saleha vision "responsive dashboard" --image mockup.png -f react`
- **Web API**: `/api/vision/generate` ab `image_b64` accept karta hai; response mein `used_vision`/`source` metadata. Hardcoded dry_run stub removed -- spec-only default ab bhi instant template preview.

### Notes
- 327 tests green. Vision HTTP layer mocked-tested; real llava run ke liye `ollama pull llava:7b` bas kafi hai.

---

## [0.9.0] - 2026-08-25 (Tier C: Capabilities Release)

### ✏️ C1: Multi-File Editor Agent
- **`saleha/core/multi_file_editor.py`**: existing repo ke kai files ko ek goal se surgically badalna -- structured JSON edit-plans, path-traversal blocking, size caps, Python syntax/safety pre-validation.
- **Atomic apply + rollback**: ek bhi write fail ho to poori transaction revert (created files delete, edited files restore).
- **Naya command `saleha edit "goal" --dir ./repo [--apply]`** (default dry-run, plan table output).

### 🌐 C2: Multi-Language Codegen
- `CoderAgent.detect_language()` -- task se TS/JS/Go/Rust/Java/Bash detection.
- Language-specific prompt rules (Go: err != nil pattern; Rust: Result/ownership; TS: no-any; ...) -- pehle sab Hindi-Python prompts the.
- TesterAgent language-aware: non-Python code par AST parse skip (valid JS ab SyntaxError nahi).

### 🔌 C3: Example Plugin
- `examples/plugins/hello_task_logger.py` -- event-hook contract ka working reference (`on_task_start` -> JSONL log). Plugin ecosystem ka seed.

---

## [0.8.0] - 2026-08-25 (Tier B: Infrastructure Release)

### 🧠 B1: Local Embeddings (True Semantic Memory)
- **`saleha/core/embedding_backends.py`**: Ollama `/api/embed` dense embeddings (default `nomic-embed-text`, `SALEHA_EMBED_MODEL` se override).
- VectorStore ab **dual-mode** hai: dense available ho to semantic search quality badh jaati hai ("throughput cap" ↔ "rate limiter" jaise matches); warna legacy TF-IDF sparse fallback (offline-safe). Mid-run degrade graceful.
- Zero-config: pehle index/search par lazy probe; koi naya dependency nahi.

### 🔐 B2: Human-In-The-Loop Approval Gate
- **`saleha/core/approval_gate.py`**: `SALEHA_APPROVAL=off|dangerous|always` env-driven gates (pehla permission attempt dead-code tha).
- Wired into **`shell_exec` tool** aur **git auto-commit** -- dangerous mode mein non-TTY par fail-closed deny, TTY par y/n confirm.
- Default `off` = purana behavior, automation kabhi nahi tootti.

### 📊 B3: Structured Metrics + CLI
- **`saleha/core/metrics.py`**: append-only JSONL (`~/.saleha/metrics.jsonl`) -- har run ka success/attempts/model/duration.
- **Naya command `saleha metrics`**: success-rate, avg attempts/duration, per-model wins table, recent-events tail (+`--json`). Orchestrator terminal outcomes auto-record hote hain.

### 🖥️ B4: Windows CI Matrix
- CI ab **ubuntu + windows × Python 3.11/3.12** (4 combos) chalata hai -- project Windows-first hai aur ab proof bhi hai. Review-bot step sirf ubuntu/py3.11 par.

---

## [0.7.0] - 2026-08-25 (Tier A: Claims -> Reality Release)

### 🧪 A1: Real Test Runner (sabse bada honesty-gap fix)
- **`saleha/core/test_runner.py`**: unittest suites ab SACH MEIN execute hoti hain (pehle sirf syntax/safety check tha). Structured JSON results -- ran/failures/tracebacks.
- `TesterAgent.run_suite()`: static gate + real execution; failure reports seedha healer/reflexion prompts mein.
- **Orchestrator `--tests` mode**: Coder se unittest suite generate hoti hai, healing loop real test failures pe heal karta hai (ab sirf "code chala" nahi -- "tests pass hue" pata hai).
- Runner apne user segments khud validate karta hai (harness footer trusted); `__main__` guard stripping built-in.

### 📡 A2: Token-Level Streaming
- `BaseAgent.think_stream(prompt, on_token=...)`: Ollama NDJSON stream se real-time token callbacks, router stats recording ke saath. Non-stream providers pe graceful fallback.
- **REPL chat ab tokens live stream karta hai** (Markdown render ki jagah).

### 🗺️ A3: AST-Ranked Context Engine
- RepoContextPacker Python files ke liye `ast.parse` based symbols use karta hai -- accurate names + line numbers + docstring relevance scoring (`def foo (L42)` format). Non-Python regex fallback retained.

### ⏯️ A4: Session Persistence & Resume
- `saleha/core/session_store.py`: har run ka checkpoint `~/.saleha/session.json`.
- **`saleha run --resume`**: crash/CTRL-C ke baad saved code + tests + attempts restore karke verification loop se continue -- planning/coding dobara nahi hoti.

---

## [0.6.0] - 2026-08-25 (Intelligence & Streaming Release)

### 🧠 Intelligence
- **Repo Context Packer (`saleha.core.repo_context_packer`)**: Aider-style repository map -- task-relevant files ko keyword/symbol/path heuristics se rank karke budget-bound context block (tree + symbol outlines + key-file excerpt) Coder prompt mein pack karta hai.
- **CLI**: `saleha run "task" --context-dir ./src` se repo-aware code generation.
- **Orchestrator**: `execute_task(context_dir=...)` param.

### 📡 Real-Time Streaming
- **TeamOrchestrator `on_event` callback**: har stage (PRD → Design → Code → Security → QA → Verification) complete hote hi turant event fire hota hai.
- **Web Studio SSE ab REAL hai**: `/api/stream/team` pehle poora workflow sync chala kar events ek saath dump karta tha -- ab stage-by-stage live stream hota hai, client-disconnect handling ke saath.

### ⚡ Performance
- **Memory Store O(N²) fix**: har save par poora vector store re-embed hota tha. Ab incremental updates (`remember`/`delete`) + lazy dirty-flag reindex (sirf next search par ek baar). Recall hits ab disk-only persist karte hain, koi vector churn nahi.

### 🐳 Sandboxing
- **Docker image preflight + auto-pull** (`ensure_image`): strict mode first-run par image absent ho to graceful `docker pull` (300s timeout), `SALEHA_DOCKER_AUTO_PULL=0` se disable.

### 🐛 Fixed
- Web server POST 401 race: body drain karke hi response bhejta hai ab (Windows WinError 10053 connection-abort flakiness eliminated).

---

## [0.5.0] - 2026-08-25 (Performance & Hygiene Release)

### ⚡ Performance
- **CLI startup 461ms → ~210ms (2.2x faster)**: `commands.py` ka eager poore-codebase import hataya gaya. Naya `_LazySymbol` proxy system heavy modules ko sirf actual use par load karta hai -- command bodies, `mock.patch(...)` targets, aur public attributes sab backward-compatible.

### 🧹 Dead Code Removal (~1,900 LOC)
- Deleted unused packages/modules: `saleha/studio/` (duplicated web server), `saleha/web/` (collaborative hub stub), `saleha/utils/` (empty), `core/permission_manager.py`, `core/model_router.py`, `core/telemetry.py` (+ inke 4 test files). Koi production code path inhe use nahi karta tha.

### 🐛 Fixed
- **Deployer bug**: generated Dockerfile ab valid CMD use karta hai (`saleha serve`) -- pehle nonexistent `saleha.web.server` module reference karta tha.
- `status` command: hardcoded `qwen3.5:0.8b` LLM health-check prompt ki jagah lightweight Ollama `/api/tags` probe + installed-model listing.
- `debug` command: duplicated validate-and-save block removed (file do baar likhi jaati thi).
- `TeamOrchestrator`: dead `DeliberationEngine()` construction removed (debate logic inline hai; instance kabhi call nahi hota tha).

### 🔒 VS Code Extension
- Webview chat XSS fix: model/user output ab `textContent` se render hota hai (`innerHTML` nahi).
- `saleha.ollamaEndpoint` setting ab webview chat mein bhi honor hoti hai (pehle hardcoded tha).

---

## [0.4.0] - 2026-08-24 (Market-Grade Upgrades)

### 🐳 Sandboxing
- **Execution Policy layer (`saleha.core.execution_policy`)**: `SALEHA_SANDBOX` env var se backend choose hota hai -- `auto` (legacy subprocess), `docker` (containerized, degrade-with-audit), ya `require-docker` (strict fail-closed). Docker runs isolated hain: no network, memory/CPU caps, pids-limit, no-new-privileges.
- `CodeExecutor` ab backend-aware hai (`ExecutionResult.backend`) aur strict mode me Docker na milne par execution refuse karta hai.

### 🧠 Intelligence
- **2026 model catalog**: SmartRouter me `qwen3-coder:30b`, `devstral:24b`, `deepseek-r1:8b`, `qwen2.5-coder:7b`, `qwen3:4b` added (legacy models retained).
- **Runtime Ollama probing**: `auto` mode router sirf actually-installed models choose karta hai (`/api/tags`, TTL-cached).
- **Complexity-tier routing wired end-to-end**: Planner ka MathLogicEngine complexity score pehle discard ho jaata tha -- ab Coder → SmartRouter tak flow karta hai.
- Router history default path fix: repo-root pollution (`./router_history.json`) → `~/.saleha/router_history.json`.

### 🌐 Providers
- **Anthropic Messages API** aur **Google Gemini generateContent API** native dispatch complete kiya (pehle advertise-only the). Cloud fallback chain me dono shamil.

### 🛡️ Security
- **Dynamic-import static detection**: `__import__("os")`, `getattr(__import__("shutil"), ...)`, `importlib.import_module(...)` patterns ab AST layer me blocked. `code_executor` ka duplicate weaker checker ek single source of truth pe delegate karta hai.
- **Swarm Security Gate enforced**: Stage-4 ka VULNERABLE verdict ab cosmetic nahi -- AST SAST cross-check + debugger remediation, phir bhi HIGH findings rahe to pipeline fail-closed.
- **Reviewer fail-closed**: LLM error par code approve nahi hota (escape hatch: `SALEHA_REVIEW_OFFLINE_PASS=1`).
- **web_fetch SSRF guard**: `file://` schemes, localhost/internal hosts, aur private/reserved resolved IPs blocked.

---

## [0.3.1] - 2026-08-24 (Security & Correctness Patch)

### 🛡️ Security
- **Web Studio API Authentication**: All `/api/*` endpoints now require an `X-Saleha-Token` header (or `?token=` for SSE). Token is auto-generated per session (print at server start) or set via `SALEHA_STUDIO_TOKEN`. The embedded UI injects the token automatically.
- **Removed wildcard CORS** (`Access-Control-Allow-Origin: *`) from the Web Studio server — closes CSRF/DNS-rebinding attack surface that exposed unauthenticated `/api/exec` (RCE) and `/api/vault/set`.
- **Sandbox hardening**: `BLOCKED_IMPORTS` now also blocks `os`, `sys`, `shutil`, `glob`, `pickle`, `marshal`, `shelve`, `sqlite3`, `signal`.
- **ThreadingHTTPServer**: long swarm/harness runs no longer block other Web Studio requests; 10 MB request-body cap added.

### 🐛 Fixed
- `memory_store`: removed duplicated `search/list_all/delete/clear` definitions; `clear()` no longer leaves a stale vector index.
- CLI: debugger REPL command renamed to `saleha debug-repl` (was silently overwriting the `saleha repl --profile` chat alias).
- `voice_assistant`: fixed nonexistent `res.error_log` attribute (`res.log`) and lazy orchestrator construction.
- `dag_engine`: default DAG referenced nonexistent profile id `agent_tester` → `agent_test_automation_engineer`.
- Harness: overall Pass@5 now uses the real unbiased estimator instead of the fake `pass_at_1 * 1.05` formula.
- Broken Rich markup closing tags in `deploy` and `browser` panel output.

### 📦 Packaging
- Declared missing runtime dependency **PyYAML** (crashed fresh installs on import); added undeclared `requests`/`psutil` to `pyproject.toml`; removed unused `fastapi`/`uvicorn` extras.
- Version unified to **0.3.x** across `__init__.py`, `setup.py`, `pyproject.toml`, Web Studio badge (now derived from package version), and VS Code extension.

---

## [0.3.0] - 2026-08-24 (Enterprise Hardening & Ecosystem Release)

### 🌟 Added
- **Encrypted Secret Vault (`saleha.core.vault`)**: PBKDF2-HMAC-SHA256 encrypted credential management with CLI commands (`saleha vault set/get/list/delete/export`).
- **Comprehensive Documentation Suite (`docs/`)**: Complete Architecture, CLI Reference, Agent Profiles, MCP Spec, Tutorials, and Security Model manuals.
- **Polyglot Execution Sandbox (`saleha.core.polyglot_executor`)**: Sandboxed execution for Python, Node.js/JavaScript, TypeScript, Go, Java, and Rust with pre-execution AST SAST checks (`saleha exec`).
- **Git Pre-Commit Security Hook (`saleha.core.git_hooks`)**: Auto-installation of `.git/hooks/pre-commit` to prevent committing vulnerable code or hardcoded secrets (`saleha git hook install`).
- **Local Model Benchmark Evaluator (`saleha.core.evaluator`)**: HumanEval-style coding benchmark suite with Pass@1 accuracy scoring (`saleha benchmark`).
- **Starter Templates (`templates/`)**: Production boilerplates for FastAPI, Express TypeScript, and Go.
- **Working Examples (`examples/`)**: Real-world implementations of Rate Limiter, CRUD API, and MCP Tool servers.
- **Packaging & Deployment**: `pyproject.toml`, multi-stage `Dockerfile`, and `docker-compose.yml`.

### 🛡️ Fixed & Hardened
- Self-healing hallucination auto-patcher for missing standard library imports and cross-language types.
- Fixed Windows `cp1252` encoding issues with ASCII-safe console streaming.
- Replaced broad `except Exception:` with granular exception classes across 30+ core modules.
- Upgraded test suite baseline to **180+ tests with 100% pass rate**.

---

## [0.2.0] - 2026-08-24 (Mega Capabilities Integration)
- Added VS Code Ghost-Text inline autocomplete (`InlineCompletionItemProvider`).
- Added One-Click SAST Quick-Fix code actions in editor.
- Added Headless Browser automation with Playwright (`saleha browser`).
- Added Git-Native Conventional Commits & safe undo (`saleha undo`).
- Added Polyglot AST parsing for JS/TS, Go, Rust, Java.

---

## [0.1.0] - 2026-08-24 (Initial Release)
- 5-Stage Multi-Agent Swarm Pipeline (`saleha team`).
- Single-goal self-healing execution loop (`saleha run`).
- 20 specialized domain agent profiles.
- Dual MCP Protocol Server & Client.
- Dark-mode Web Studio (`saleha serve`) and Terminal TUI (`saleha tui`).
