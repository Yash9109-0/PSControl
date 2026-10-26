@echo off
setlocal
title Open Firewall for ps2-party-pad

rem ── Check if already running as administrator ───────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  This script needs administrator privileges to modify the firewall.
    echo  Windows will show a "User Account Control" pop-up — click Yes.
    echo.
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

rem ── Running as administrator from here ──────────────────────────────

echo.
echo  Adding Windows Firewall rule ...
echo.

rem Remove old rule if it exists (avoids duplicates on re-run)
netsh advfirewall firewall delete rule name="ps2-party-pad (TCP 8000)" >nul 2>&1

rem Add new inbound rule — private networks only
netsh advfirewall firewall add rule ^
    name="ps2-party-pad (TCP 8000)" ^
    dir=in ^
    action=allow ^
    protocol=TCP ^
    localport=8000 ^
    profile=private ^
    description="Allow phones to reach the ps2-party-pad server on port 8000"

if %errorlevel% equ 0 (
    echo.
    echo  SUCCESS: Firewall rule "ps2-party-pad (TCP 8000)" added.
    echo  Inbound TCP on port 8000 is now allowed on private networks.
) else (
    echo.
    echo  ERROR: Could not add the firewall rule. See the message above.
)

echo.
echo  ── Verifying ──
netsh advfirewall firewall show rule name="ps2-party-pad (TCP 8000)" | findstr /i "Rule Name Enabled Direction Profiles" 2>nul
echo.

pause
