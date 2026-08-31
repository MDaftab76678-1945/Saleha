#!/usr/bin/env bash
# Saleha AI Universal Shell Installer for Linux & macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/MDaftab76678-1945/Saleha/main/install.sh | bash

set -e

echo -e "\033[1;36m============================================================\033[0m"
echo -e "\033[1;33m⚡ Installing Saleha AI Autonomous Engineering Platform ⚡\033[0m"
echo -e "\033[1;36m============================================================\033[0m"

# 1. Check Python
PYTHON_BIN=""
if command -v python3 &> /dev/null; then
    PYTHON_BIN="python3"
elif command -v python &> /dev/null; then
    PYTHON_BIN="python"
else
    echo -e "\033[1;31m❌ Python 3.9+ is required but not found.\033[0m"
    echo "Please install Python from https://www.python.org/downloads/"
    exit 1
fi

echo -e "\033[1;32m✅ Python detected: $($PYTHON_BIN --version)\033[0m"

# 2. Check Ollama
if command -v ollama &> /dev/null; then
    echo -e "\033[1;32m✅ Ollama detected\033[0m"
else
    echo -e "\033[1;33m⚠️ Ollama not detected. Install from https://ollama.ai for local AI.\033[0m"
fi

# 3. Pip Install
echo -e "\033[1;36m📦 Installing Saleha...\033[0m"
$PYTHON_BIN -m pip install --upgrade pip
$PYTHON_BIN -m pip install -e .

echo -e "\n\033[1;36m============================================================\033[0m"
echo -e "\033[1;32m🎉 Saleha AI successfully installed!\033[0m"
echo -e "\033[1;33mRun 'saleha --version' or 'saleha hud' to launch.\033[0m"
echo -e "\033[1;36m============================================================\033[0m"
