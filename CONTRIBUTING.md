# 🤝 Contributing to Saleha AI

Thank you for contributing to Saleha AI! We welcome bug reports, feature enhancements, new agent personas, and documentation improvements.

---

## 🛠️ Development Setup

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/aftab-alam/saleha-0.1.git
   cd saleha-0.1
   ```

2. **Create a virtual environment and install in editable mode:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   pip install -e .
   ```

3. **Install Git Pre-Commit Hook:**
   ```powershell
   saleha git hook install
   ```

---

## 🧪 Running Tests

Before submitting any Pull Request, ensure that all automated unit tests pass:

```powershell
python -m unittest discover -s saleha/tests -v
```

---

## 🌿 Pull Request Workflow

1. Fork the repo and create your branch from `main`:
   ```powershell
   git checkout -b feat/my-new-feature
   ```
2. Commit your changes following Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`).
3. Push to your fork and submit a Pull Request.

