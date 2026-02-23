# AutoTrade AI - Windows Production Deployment (Current System)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " AutoTrade AI - Windows Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"

# Configuration
$AppDir = "C:\Users\dtrid8\development\autotrade-ai"
$VenvPath = "$AppDir\.venv"
$LogDir = "$AppDir\logs"
$DataDir = "$AppDir\data"

# Check current location
if ((Get-Location).Path -ne $AppDir) {
    Write-Host "Changing to application directory..." -ForegroundColor Yellow
    Set-Location $AppDir
}

# Create directories
Write-Host "Creating directories..." -ForegroundColor Yellow
@($LogDir, $DataDir, "$DataDir\backups") | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Path $_ -Force | Out-Null
        Write-Host "[OK] Created $_" -ForegroundColor Green
    }
}

# Check Python virtual environment
if (-not (Test-Path $VenvPath)) {
    Write-Host "[ERROR] Virtual environment not found at $VenvPath" -ForegroundColor Red
    Write-Host "Run: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK] Virtual environment found" -ForegroundColor Green

# Kill existing processes
Write-Host ""
Write-Host "Stopping existing processes..." -ForegroundColor Yellow
$pythonProcs = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*autotrade-ai*"
}

if ($pythonProcs) {
    $pythonProcs | ForEach-Object {
        Write-Host "  Stopping process ID: $($_.Id)" -ForegroundColor Yellow
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    Write-Host "[OK] Existing processes stopped" -ForegroundColor Green
} else {
    Write-Host "[OK] No existing processes found" -ForegroundColor Green
}

# Check .env file
if (-not (Test-Path ".env")) {
    Write-Host "[WARNING] .env file not found" -ForegroundColor Yellow
    Write-Host "Creating from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[ACTION REQUIRED] Edit .env file with your credentials" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] .env file found" -ForegroundColor Green

# Start main trading system
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Starting Trading System" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Create startup script
$StartScript = @"
Set-Location '$AppDir'
& '$VenvPath\Scripts\Activate.ps1'
python main.py
"@

$StartScript | Out-File -FilePath "$AppDir\start_trading.ps1" -Encoding UTF8 -Force

# Start in new window
Write-Host "Launching trading system in new window..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-File", "$AppDir\start_trading.ps1" -WindowStyle Normal

Start-Sleep -Seconds 3

# Check if started
$newProcs = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*autotrade-ai*"
}

if ($newProcs) {
    Write-Host "[OK] Trading system started (PID: $($newProcs[0].Id))" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to start trading system" -ForegroundColor Red
    exit 1
}

# Start monitoring dashboard
Write-Host ""
Write-Host "Starting monitoring dashboard..." -ForegroundColor Yellow

$MonitorScript = @"
Set-Location '$AppDir'
& '$VenvPath\Scripts\Activate.ps1'
python live_monitor.py
"@

$MonitorScript | Out-File -FilePath "$AppDir\start_monitor.ps1" -Encoding UTF8 -Force

Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-File", "$AppDir\start_monitor.ps1" -WindowStyle Normal

Write-Host "[OK] Monitoring dashboard launched" -ForegroundColor Green

# Display status
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "System Status:" -ForegroundColor Yellow
Write-Host "  Trading System: Running in separate window"
Write-Host "  Live Monitor: Running in separate window"
Write-Host "  Database: $AppDir\autotrade.db"
Write-Host "  Logs: $LogDir"
Write-Host ""
Write-Host "Management Commands:" -ForegroundColor Yellow
Write-Host "  View running processes:"
Write-Host "    Get-Process python | Where-Object {`$_.Path -like '*autotrade-ai*'}"
Write-Host ""
Write-Host "  Stop all:"
Write-Host "    Get-Process python | Where-Object {`$_.Path -like '*autotrade-ai*'} | Stop-Process"
Write-Host ""
Write-Host "  View logs:"
Write-Host "    Get-Content logs\trading_$(Get-Date -Format 'yyyy-MM-dd').log -Tail 50 -Wait"
Write-Host ""
Write-Host "  Database:"
Write-Host "    sqlite3 autotrade.db"
Write-Host ""
Write-Host "Configuration File: .env" -ForegroundColor Yellow
Write-Host "Documentation: DEPLOYMENT.md, LIVE_IMPLEMENTATION.md" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Create status check script
$StatusScript = @'
Write-Host ""
Write-Host "=== AutoTrade AI System Status ===" -ForegroundColor Cyan
Write-Host ""

$procs = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*autotrade-ai*"
}

if ($procs) {
    Write-Host "Running Processes:" -ForegroundColor Green
    $procs | Format-Table Id, ProcessName, StartTime, @{Name="Memory(MB)";Expression={[math]::Round($_.WorkingSet64/1MB,2)}} -AutoSize
} else {
    Write-Host "No processes running" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Recent Log Entries:" -ForegroundColor Cyan
$logFile = "logs\trading_$(Get-Date -Format 'yyyy-MM-dd').log"
if (Test-Path $logFile) {
    Get-Content $logFile -Tail 10
} else {
    Write-Host "No log file found for today" -ForegroundColor Yellow
}

Write-Host ""
'@

$StatusScript | Out-File -FilePath "$AppDir\check_status.ps1" -Encoding UTF8 -Force

Write-Host "Created status check script: .\check_status.ps1" -ForegroundColor Green
Write-Host "Run: .\check_status.ps1" -ForegroundColor Yellow
Write-Host ""
