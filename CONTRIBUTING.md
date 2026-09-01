# 🤝 Contributing to Saleha

Thanks for considering a contribution! Saleha is a **local-first autonomous multi-agent platform** — every contribution must keep the "runs 100% on your machine, no cloud required" promise intact.

## 🚀 Quick Setup

```bash
git clone https://github.com/MDaftab76678-1945/Saleha.git
cd Saleha
python -m pip install -e .
python -m pip install pytest pytest-asyncio
ollama pull qwen2.5-coder:7b            # fast local model for manual testing
```

## ✅ Before Opening a PR

1. **Tests pass:**
   ```bash
   python -m pytest saleha/tests/ -q
   ```
2. **Review-AI passes:**
   ```bash
   saleha review-ai <modified_file>
   ```
3. **No new mandatory dependencies.** Heavy capabilities go into extras with graceful fallback.
4. **Security posture:** code execution must respect sandbox policies (`saleha/core/sandbox_runner.py`) and constitutional AI rails (`saleha/core/constitutional_guard.py`).
5. **CHANGELOG.md** — add a line under `Unreleased`.

## 🧪 Testing Notes

- LLM calls are always mocked in unit tests (offline deterministic testing).
- CI runs on **Ubuntu + Windows** across Python 3.10, 3.11, 3.12 (780+ tests).

## 📜 License

MIT License. By contributing you agree your work is released under MIT.
