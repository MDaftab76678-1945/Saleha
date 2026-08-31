# One-Click Windows PowerShell Installer for Saleha AI Platform
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  🧠 SALEHA AI - PLATFORM INSTALLER (WINDOWS)" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# 1. Check Python
$pythonCmd = "python"
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} else {
    Write-Host "❌ Python is not installed. Please install Python 3.9+ from https://python.org" -ForegroundColor Red
    Exit 1
}

# 2. Install dependencies
Write-Host "📦 Installing requirements via $pythonCmd..." -ForegroundColor Green
& $pythonCmd -m pip install --upgrade pip --quiet
& $pythonCmd -m pip install -r requirements.txt

# 3. Install in editable mode
Write-Host "⚡ Installing Saleha in editable development mode..." -ForegroundColor Green
& $pythonCmd -m pip install -e .

# 4. Verify installation
Write-Host "🧪 Verifying Saleha CLI..." -ForegroundColor Green
saleha --version

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "✅ Saleha AI Platform Installed Successfully!" -ForegroundColor Green
Write-Host "👉 Run 'saleha run --help' or 'saleha serve' to begin." -ForegroundColor Yellow
Write-Host "=============================================" -ForegroundColor Cyan

