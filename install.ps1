# Saleha AI Universal PowerShell Installer for Windows
# Usage: irm https://raw.githubusercontent.com/MDaftab76678-1945/Saleha/main/install.ps1 | iex

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "⚡ Installing Saleha AI Autonomous Engineering Platform ⚡" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $pythonCmd) {
    Write-Host "❌ Python 3.9+ is required but not found in PATH." -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Python detected: $($pythonCmd.Source)" -ForegroundColor Green

# 2. Check Ollama
$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaCmd) {
    Write-Host "✅ Ollama detected: $($ollamaCmd.Source)" -ForegroundColor Green
} else {
    Write-Host "⚠️ Ollama not detected. Install Ollama from https://ollama.ai for local AI models." -ForegroundColor Yellow
}

# 3. Pip Install Saleha
Write-Host "📦 Installing Saleha dependencies..." -ForegroundColor Cyan
& $pythonCmd.Source -m pip install --upgrade pip
& $pythonCmd.Source -m pip install -e .

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "🎉 Saleha AI successfully installed!" -ForegroundColor Green
Write-Host "Run 'saleha --version' or 'saleha hud' to get started." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
