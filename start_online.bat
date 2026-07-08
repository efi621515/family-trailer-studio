@echo off
title Family Trailer Studio (Online)
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

rem require a family password before exposing to the internet
if not defined FTS_PASSWORD (
  echo.
  echo   ============================================================
  echo   Before going online you must set a family password.
  echo   Open a normal terminal ^(PowerShell^) and run once:
  echo.
  echo       setx FTS_PASSWORD "your-family-word"
  echo.
  echo   Then close it, and run this launcher again.
  echo   ============================================================
  echo.
  pause
  exit /b
)

rem free port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

where python >nul 2>&1
if %errorlevel%==0 (set PY=python) else (set PY=py)

rem start the app server in its own window
start "Family Trailer Studio - server" %PY% -m server.app

rem wait for the server, then open the public tunnel
timeout /t 4 >nul
echo.
echo   ============================================================
echo      Family Trailer Studio - ONLINE
echo   ------------------------------------------------------------
echo   A public link will appear below (look for trycloudflare.com).
echo   Share that link + the family password with your family.
echo.
echo   Keep BOTH windows open while in use.
echo   To stop: close both windows.
echo   ============================================================
echo.
cloudflared.exe tunnel --url http://localhost:8000
pause
