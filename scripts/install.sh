#!/bin/bash
# One-Click Linux/macOS Installer for Saleha AI Platform
set -e

echo "============================================="
echo "  🧠 SALEHA AI - PLATFORM INSTALLER"
echo "============================================="

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.9+."
    exit 1
fi

# 2. Install requirements
echo "📦 Installing requirements..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# 3. Install Saleha in editable mode
echo "⚡ Installing Saleha..."
python3 -m pip install -e .

# 4. Verify installation
echo "🧪 Verifying Saleha CLI..."
saleha --version

echo "============================================="
echo "✅ Saleha AI Platform Installed Successfully!"
echo "👉 Run 'saleha run --help' or 'saleha serve' to begin."
echo "============================================="

