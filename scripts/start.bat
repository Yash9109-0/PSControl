@echo off
setlocal enabledelayedexpansion
title ps2-party-pad Server
cd /d "%~dp0.."

rem ── Check Python ────────────────────────────────────────────────────
echo.
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python is not installed or not in your PATH.
    echo.
    echo  How to fix:
    echo    1. Download Python from https://www.python.org/downloads/
    echo    2. During installation, CHECK the box "Add python.exe to PATH"
    echo    3. Restart your PC, then double-click this file again.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do (
    echo  Python %%v found.
)

rem ── Create virtual environment on first run ─────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo  Creating virtual environment (.venv) ...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
)

rem ── Activate the venv ───────────────────────────────────────────────
call .venv\Scripts\activate.bat

rem ── Install / update requirements ───────────────────────────────────
if not exist ".venv\Lib\site-packages\fastapi" (
    echo.
    echo  Installing requirements (first run only) ...
    pip install --quiet -r requirements.txt
    if %errorlevel% neq 0 (
        echo  ERROR: pip install failed. Check the output above.
        pause
        exit /b 1
    )
    echo  Done.
)

rem ── ViGEmBus check ──────────────────────────────────────────────────
echo.
reg query "HKLM\SOFTWARE\Nefarius Software Solutions e.U.\ViGEmBus" >nul 2>&1
if %errorlevel% neq 0 (
    echo  ************************************************************
    echo  *  WARNING: ViGEmBus driver not found.                     *
    echo  *                                                          *
    echo  *  The server will start, but virtual gamepads won't work  *
    echo  *  until you install the driver.                           *
    echo  *                                                          *
    echo  *  Download it from:                                       *
    echo  *  https://github.com/ViGEm/ViGEmBus/releases             *
    echo  *                                                          *
    echo  *  Install, reboot, then run this script again.            *
    echo  ************************************************************
    echo.
)

rem ── Determine the join URL ──────────────────────────────────────────
set "JOIN_IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    if not defined JOIN_IP (
        set "JOIN_IP=%%a"
        rem Trim leading space
        set "JOIN_IP=!JOIN_IP: =!"
    )
)
if not defined JOIN_IP set "JOIN_IP=127.0.0.1"

echo  ================================================================
echo.
echo   Host dashboard : http://localhost:8000/host   (opens in browser)
echo   Join URL       : http://!JOIN_IP!:8000/
echo.
echo   Share the Join URL with players, or they can scan the QR code
echo   shown on the host dashboard.
echo.
echo  ================================================================
echo.
echo  Press Ctrl+C to stop the server.
echo.

rem ── Open the host dashboard ─────────────────────────────────────────
start "" "http://localhost:8000/host"

rem ── Start the server ────────────────────────────────────────────────
python -m server
