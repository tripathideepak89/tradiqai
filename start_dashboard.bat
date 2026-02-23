@echo off
REM AutoTrade AI Dashboard Launcher
REM This script starts the web dashboard for real-time monitoring

echo ========================================
echo   AutoTrade AI - Dashboard Launcher
echo ========================================
echo.

REM Activate virtual environment
echo [1/3] Activating virtual environment...
call .venv\Scripts\activate.bat

REM Set encoding for Unicode support
echo [2/3] Configuring environment...
set PYTHONIOENCODING=utf-8

REM Start dashboard
echo [3/3] Starting dashboard server...
echo.
echo Dashboard will be available at:
echo   http://localhost:8080
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

python dashboard.py

pause
