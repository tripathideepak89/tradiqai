@echo off
cd /d C:\Users\dtrid8\development\autotrade-ai
set LOGFILE=C:\Users\dtrid8\development\autotrade-ai\logs\dre_cron.log
if not exist C:\Users\dtrid8\development\autotrade-ai\logs mkdir C:\Users\dtrid8\development\autotrade-ai\logs
echo ============================= >> %LOGFILE%
echo %date% %time% - DRE Cron Start >> %LOGFILE%
.venv\Scripts\python.exe dre_cron.py >> %LOGFILE% 2>&1
echo %date% %time% - DRE Cron End (exit: %errorlevel%) >> %LOGFILE%
