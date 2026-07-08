@echo off
setlocal

cd /d "%~dp0"

echo Stopping ai-change-map services...
echo.

for %%F in (backend frontend ngrok) do (
    if exist ".runtime\%%F.pid" (
        set /p PID=<".runtime\%%F.pid"
        call :killtree %%F
    ) else (
        echo %%F pid file not found.
    )
)

echo.
echo Done.
pause
exit /b 0

:killtree
echo Stopping %1 PID %PID% ...
taskkill /PID %PID% /T /F >nul 2>nul
if errorlevel 1 (
    echo %1 was not running or could not be stopped.
) else (
    echo %1 stopped.
)
exit /b 0
