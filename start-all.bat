@echo off
setlocal

cd /d "%~dp0"

echo Starting ai-change-map...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-all.ps1"

echo.
echo If startup failed, check the messages above and logs in .runtime.
echo This window can be closed after you have copied the ngrok URL.
pause
