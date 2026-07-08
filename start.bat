@echo off
title Family Trailer Studio
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

rem free port 8000 if anything is holding it
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

rem pick a python launcher
where python >nul 2>&1
if %errorlevel%==0 (set PY=python) else (set PY=py)

echo.
echo   ==========================================
echo      Family Trailer Studio
echo   ==========================================
echo.
echo   Starting... your browser will open automatically.
echo   If not, open:  http://127.0.0.1:8000
echo.
echo   To stop the app: close this window.
echo.
%PY% -m server.app

echo.
echo   The app has stopped. You can close this window.
pause
