@echo off
REM ============================================================
REM  CareLock Sync — One-Click Demo Launcher
REM  Run this file as Administrator for best results
REM ============================================================
title CareLock Sync Demo

echo.
echo  ██████╗ █████╗ ██████╗ ███████╗██╗      ██████╗  ██████╗██╗  ██╗
echo  ██╔════╝██╔══██╗██╔══██╗██╔════╝██║     ██╔═══██╗██╔════╝██║ ██╔╝
echo  ██║     ███████║██████╔╝█████╗  ██║     ██║   ██║██║     █████╔╝
echo  ██║     ██╔══██║██╔══██╗██╔══╝  ██║     ██║   ██║██║     ██╔═██╗
echo  ╚██████╗██║  ██║██║  ██║███████╗███████╗╚██████╔╝╚██████╗██║  ██╗
echo   ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝
echo.
echo  Secure Hospital Database Synchronisation — FYP Demo
echo  ============================================================
echo.

REM ── Step 1: Start databases ────────────────────────────────────────────
echo [1/4] Starting PostgreSQL databases...
docker compose -f "%~dp0docker-compose-demo.yml" up -d
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  ERROR: Docker not running or docker-compose failed.
    echo  Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)
echo        Databases starting (waiting 8 seconds)...
timeout /t 8 /nobreak > nul
echo        [OK] Databases ready

REM ── Step 2: Install Python deps ───────────────────────────────────────
echo.
echo [2/4] Checking Python dependencies...
cd /d "%~dp0backend"
if exist venv\Scripts\python.exe (
    set PYTHON="%~dp0backend\venv\Scripts\python.exe"
    set PIP="%~dp0backend\venv\Scripts\pip.exe"
) else (
    set PYTHON=python
    set PIP=pip
)
%PIP% install fastapi uvicorn pydantic python-dotenv chromadb google-generativeai --quiet 2>nul
echo        [OK] Dependencies checked

REM ── Step 3: Start backend ─────────────────────────────────────────────
echo.
echo [3/4] Starting CareLock API server (port 8000)...
start "CareLock API" cmd /k "%PYTHON% -m uvicorn demo_server:app --host 0.0.0.0 --port 8000 --reload"
echo        Waiting for API to start (5 seconds)...
timeout /t 5 /nobreak > nul
echo        [OK] API running at http://localhost:8000
echo        [OK] API Docs at   http://localhost:8000/docs

REM ── Step 4: Start frontend ────────────────────────────────────────────
echo.
echo [4/4] Starting React frontend (port 5173)...
cd /d "%~dp0frontend-app"
if not exist node_modules (
    echo        Installing npm packages (first run — takes 1-2 minutes)...
    call npm install --legacy-peer-deps
)
start "CareLock Frontend" cmd /k "npm run dev"
echo        Waiting for frontend to start (8 seconds)...
timeout /t 8 /nobreak > nul

REM ── Done ──────────────────────────────────────────────────────────────
echo.
echo  ============================================================
echo   CARELOCK SYNC IS READY FOR DEMO
echo  ============================================================
echo.
echo   Frontend:    http://localhost:5173
echo   API:         http://localhost:8000
echo   API Docs:    http://localhost:8000/docs
echo.
echo   Login with:  admin@carelock.demo  /  any-password
echo.
echo   Demo flow:   1. Login
echo                2. Click "Live Demo" in sidebar
echo                3. Click "Auto-play full demo"
echo                4. Explore all 6 pages
echo  ============================================================
echo.
echo  Opening browser...
timeout /t 3 /nobreak > nul
start "" http://localhost:5173

echo.
echo  Press any key to STOP all services...
pause > nul

REM ── Cleanup ───────────────────────────────────────────────────────────
echo.
echo  Stopping services...
taskkill /FI "WINDOWTITLE eq CareLock API*" /F > nul 2>&1
taskkill /FI "WINDOWTITLE eq CareLock Frontend*" /F > nul 2>&1
cd /d "%~dp0"
docker compose -f docker-compose-demo.yml down
echo  All services stopped. Goodbye.
