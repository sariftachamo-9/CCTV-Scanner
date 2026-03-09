@echo off
setlocal enabledelayedexpansion
title CCTV ^& Infra Scanner Pro - Control Center
color 0B

:: Check for Administrator Privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo [!] CRITICAL: This application requires Administrator Privileges.
    echo [!] Please right-click this file and select "Run as Administrator".
    echo.
    pause
    exit /b
)

:: Prompt for Remote Access
cls
echo ======================================================
echo    📡 CCTV ^& INFRA SCANNER PRO - ACCESS OPTIONS
echo ======================================================
echo.
echo [1] Local Access Only (Standard)
echo [2] Enable Remote Access (Via Cloudflare Tunnel)
echo.
set /p access_choice="Select access mode [1-2]: "

if "%access_choice%"=="2" (
    echo.
    echo [!] INITIALIZING CLOUDFLARE TUNNEL...
    echo [!] Generating secure Remote Access URL. Please wait...
    
    if exist cloudflare.log del cloudflare.log
    start /B "" cmd /c "cloudflared tunnel --url http://127.0.0.1:5001 > cloudflare.log 2>&1"
    
    set "cf_url="
    for /L %%i in (1,1,20) do (
        if not defined cf_url (
            timeout /t 1 /nobreak >nul
            for /f "tokens=4 delims= " %%a in ('type cloudflare.log 2^>nul ^| findstr "https://.*trycloudflare.com"') do (
                set "cf_url=%%a"
            )
        )
    )
    
    if defined cf_url (
        echo.
        echo ======================================================
        echo     🌐 REMOTE ACCESS URL ACTIVE
        echo ======================================================
        echo  !cf_url!
        echo ======================================================
        echo.
    ) else (
        echo [!] Timeout waiting for Cloudflare URL. Check cloudflare.log
    )
)

cls
echo ======================================================
echo    📡 CCTV ^& INFRA SCANNER PRO - STARTUP
echo ======================================================
echo.

:: Clean up existing processes on port 5001
echo [STP 1/3] Optimizing Network Environment...
taskkill /F /IM cloudflared.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5001') do (
    echo [!] Reclaiming port 5001 (Terminating SID: %%a)...
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: Launch the Flask backend
echo [STP 2/3] Launching Security Core...
start "Scanner Backend" /B cmd /c "python app.py"

:: Wait for initialization
echo [STP 3/3] Synchronizing with Dashboard...
:check_server
timeout /t 2 /nobreak >nul
netstat -ano | findstr :5001 >nul
if %errorLevel% neq 0 (
    set /a attempt+=1
    if !attempt! gtr 5 (
        echo [!] ERROR: Backend failed to start. Check your Python environment.
        pause
        exit /b
    )
    goto check_server
)

:: Open the browser UI
echo.
echo [✓] SUCCESS: Core Engine Active.
echo [✓] Dashboard: http://localhost:5001
echo.
start http://localhost:5001

echo ======================================================
echo    SYSTEM STATUS: [ ACTIVE ]
echo    THEME SUPPORT: [ ENABLED ]
echo.
echo    Minimize this window but DO NOT close it.
echo    Use "Stop & Exit" button in browser to shut down.
echo ======================================================
echo.
pause
