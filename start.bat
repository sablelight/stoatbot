@echo off
setlocal EnableDelayedExpansion
title Stoat Bot Launcher

echo ============================================
echo           STOAT BOT LAUNCHER
echo ============================================
echo.

:: ── Check Python ─────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Python %PY_VER% found.

:: ── Check pip ────────────────────────────────
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not found. Attempting to install...
    python -m ensurepip --upgrade
)

:: ── Always verify aiosqlite is present ───────
python -c "import aiosqlite" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [UPDATE] Missing dependencies detected. Installing now...
    echo.
    pip install --upgrade pip >nul 2>&1
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install dependencies!
        echo Check your internet connection and try again.
        pause
        exit /b 1
    )
    echo.
    echo [OK] Dependencies installed successfully!
) else (
    echo [OK] Dependencies already installed. Skipping.
)

:: ── Bot token input ───────────────────────────
echo.

set TOKEN_FILE=.bot_token
set BOT_TOKEN=

if exist "%TOKEN_FILE%" (
    set /p BOT_TOKEN=<"%TOKEN_FILE%"
    echo [OK] Saved bot token found.
    echo.
    echo Current token: !BOT_TOKEN!
    echo.
    set /p CHANGE_TOKEN="Enter a new token to change it, or press ENTER to keep it: "
    if not "!CHANGE_TOKEN!"=="" (
        set BOT_TOKEN=!CHANGE_TOKEN!
        echo !BOT_TOKEN!>"%TOKEN_FILE%"
        echo [OK] Token updated.
    )
) else (
    echo No bot token saved yet.
    echo You can find your token in your Stoat developer dashboard.
    echo.
    :ASK_TOKEN
    set /p BOT_TOKEN="Enter your bot token: "
    if "!BOT_TOKEN!"=="" (
        echo [ERROR] Token cannot be empty. Please enter your bot token.
        goto ASK_TOKEN
    )
    echo !BOT_TOKEN!>"%TOKEN_FILE%"
    echo [OK] Token saved.
)

:: ── Write .env ────────────────────────────────
echo BOT_TOKEN=!BOT_TOKEN!> .env
echo PREFIX=^!>> .env

echo.
echo [OK] Database: stoat.db (local file, no setup needed^)

:: ── Launch ────────────────────────────────────
echo.
echo ============================================
echo  Starting Stoat Bot...
echo  Press Ctrl+C to stop.
echo ============================================
echo.

:RESTART_LOOP
python bot.py
set EXIT_CODE=!errorlevel!

if !EXIT_CODE! NEQ 0 (
    echo.
    echo [WARN] Bot exited with code !EXIT_CODE!.
    echo Restarting in 5 seconds... (Ctrl+C to cancel^)
    timeout /t 5 /nobreak >nul
    goto RESTART_LOOP
)

echo.
echo [INFO] Bot stopped cleanly.
pause
