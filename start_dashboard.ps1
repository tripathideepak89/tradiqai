# AutoTrade AI Dashboard Launcher (PowerShell)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AutoTrade AI - Dashboard Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
Write-Host "[1/3] Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Set encoding for Unicode support
Write-Host "[2/3] Configuring environment..." -ForegroundColor Yellow
$env:PYTHONIOENCODING = "utf-8"

# Start dashboard
Write-Host "[3/3] Starting dashboard server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Dashboard will be available at:" -ForegroundColor Green
Write-Host "  http://localhost:8080" -ForegroundColor Green -BackgroundColor Black
Write-Host ""
Write-Host "Opening browser..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
Start-Process "http://localhost:8080"
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Run dashboard
python dashboard.py
