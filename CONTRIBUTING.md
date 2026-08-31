# 🤝 Contributing to Saleha

Thanks for considering a contribution! Saleha is a **local-first autonomous multi-agent platform** — every contribution must keep the "runs 100% on your machine, no cloud required" promise intact.

## 🚀 Quick Setup

```bash
git clone https://github.com/MDaftab76678-1945/Saleha.git
cd Saleha
python -m pip install -e .
python -m pip install -e ".[codeintel]"   # optional: tree-sitter context ranking
ollama pull qwen2.5-coder:1.5b            # fast local model for manual testing
```

## ✅ Before Opening a PR

1. **Tests pass:**
   ```bash
   python -m unittest discover -s saleha/tests
   ```
2. **No new mandatory dependencies.** Heavy capabilities go into extras:
   `[browser]`, `[voice]`, `[codeintel]` — with graceful degradation when absent.
3. **Security posture:** anything that executes generated code must respect
   `SALEHA_SANDBOX` (see `saleha/core/execution_policy.py`) and pass through
   `approval_gate` if it's a destructive action.
4. **Docs:** new CLI command? Re-run `python scripts/gen_cli_docs.py`.
5. **CHANGELOG.md** — add a line under `Unreleased`.

## 🧪 Testing Notes

- LLM calls are always mocked in unit tests (never require Ollama).
- Real-subprocess tests exist (`test_real_test_runner.py`) — they run offline.
- CI runs on **ubuntu + windows**, Python 3.11 & 3.12 — keep paths cross-platform
  (use `saleha/core/path_utils.py:safe_relpath`, never raw `os.path.relpath`
  across user-provided roots).

## 🏗️ Project Layout

```
saleha/
├── agents/        # BaseAgent + Planner/Coder/Tester/Reviewer/Debugger
├── core/          # engines: orchestrator pieces, router, sandbox, memory...
├── cli/           # Click commands (lazy-loaded), REPL, dashboard, TUI
├── server/        # Web Studio (token-authenticated REST/SSE)
├── harness/       # benchmark evaluation (Pass@k)
├── skills/        # agent profiles + instant local skills
└── tests/         # 346 tests, fully offline
```

## 🎯 Code Style

- Type hints on public functions.
- Comments may be Hinglish (project convention) — code identifiers English.
- No import-time heavy work; use lazy loading (`_LazySymbol` pattern in CLI).

## 📜 License

MIT — by contributing you agree your work is released under MIT.
