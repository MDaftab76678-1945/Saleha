# Contributing to Saleha

Thanks for considering a contribution! Saleha is a **local-first autonomous multi-agent platform** — every contribution must keep the "runs 100% on your machine, no cloud required" promise intact.

## Quick Setup

```bash
git clone https://github.com/MDaftab76678-1945/Saleha.git
cd Saleha
python -m pip install -e ".[dev,formal]"   # [formal] brings Z3
ollama pull qwen2.5-coder:3b               # the primary local coder model
```

## Before Opening a PR

1. **Tests pass:**

   ```bash
   PYTHONIOENCODING=utf-8 python -m pytest saleha/tests/ -q
   ```

2. **Review-AI passes:**

   ```bash
   saleha review-ai <modified_file>
   ```

3. **No new mandatory dependencies.** Heavy capabilities go into extras with graceful fallback.
4. **Security posture:** code execution must respect sandbox policies (`saleha/core/harness/sandbox_runner.py`) and the rule-based audit in `saleha/core/security/constitutional_guard.py`.
   The commit gate `python .agents/scripts/preflight_lint.py` must pass.
5. **CHANGELOG.md** — add a line under `Unreleased`.

## Testing Notes

- LLM calls are always mocked in unit tests (offline deterministic testing).
- CI runs on **Ubuntu + Windows** across Python 3.12, 3.13 and 3.14 (see
  `.github/workflows/ci.yml`). `requires-python` is `>=3.12`; 3.10 and 3.11
  are not supported.

## License

MIT License. By contributing you agree your work is released under MIT.
