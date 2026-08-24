# 🧠 Saleha AI - VS Code Extension Bridge

Connect your VS Code editor directly to the **Saleha Autonomous Multi-Agent Engineering Platform**.

## ✨ Features
- **One-Click AST SAST Security Scan**: Right-click in any file and select `"Saleha: Run AST Security SAST Audit"`.
- **Autonomous Swarm Delivery**: Trigger 5 domain agents (PM $\rightarrow$ Architect $\rightarrow$ SDE $\rightarrow$ Security $\rightarrow$ QA) from inside your editor.
- **Autonomous Pull Requests**: Generate branches, conventional commits, and PR packages.
- **Embedded Web Studio**: Instant access to Saleha's real-time SSE Web Studio from the status bar.

## 🚀 Getting Started
1. Ensure Saleha CLI is installed:
   ```bash
   pip install -e .
   ```
2. Start the local server if using the Web Studio:
   ```bash
   saleha serve
   ```
3. Use VS Code Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) and type `Saleha`.

