# ============================================================
#  CareLock Sync — One-Click Demo Launcher (PowerShell)
#  Usage:  Right-click → Run with PowerShell
#           OR: Open PowerShell here, run: .\START_DEMO.ps1
# ============================================================

$ErrorActionPreference = "Continue"
$ROOT = $PSScriptRoot

Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Cyan
Write-Host "   CareLock Sync — FYP Demo Launcher" -ForegroundColor Cyan
Write-Host "   Secure Hospital Database Synchronisation" -ForegroundColor Cyan
Write-Host "  ============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Databases ─────────────────────────────────────────────────────────
Write-Host "[1/4] Starting PostgreSQL databases..." -ForegroundColor Yellow
try {
    docker compose -f "$ROOT\docker-compose-demo.yml" up -d
    Write-Host "      Waiting 8 seconds for databases to be ready..." -ForegroundColor Gray
    Start-Sleep -Seconds 8
    Write-Host "      [OK] Databases running" -ForegroundColor Green
} catch {
    Write-Host "      ERROR: Docker not running. Please start Docker Desktop." -ForegroundColor Red
    Write-Host "      Continuing without databases (demo server uses mock data)." -ForegroundColor Yellow
}

# ── Step 2: Python deps ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/4] Checking Python dependencies..." -ForegroundColor Yellow
Push-Location "$ROOT\backend"

$pythonExe = "python"
if (Test-Path "venv\Scripts\python.exe") {
    $pythonExe = ".\venv\Scripts\python.exe"
}
$pipExe = if ($pythonExe -eq "python") { "pip" } else { ".\venv\Scripts\pip.exe" }

# Install minimal required packages silently
& $pipExe install fastapi uvicorn pydantic python-dotenv chromadb 2>&1 | Out-Null
Write-Host "      [OK] Dependencies ready" -ForegroundColor Green

# ── Step 3: Backend ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] Starting CareLock API server on port 8000..." -ForegroundColor Yellow
$backendJob = Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ROOT\backend'; Write-Host 'CareLock API Server' -ForegroundColor Cyan; & '$pythonExe' -m uvicorn demo_server:app --host 0.0.0.0 --port 8000 --reload"
) -PassThru
Write-Host "      Waiting 5 seconds for API to start..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Test if API is up
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3
    Write-Host "      [OK] API running: http://localhost:8000" -ForegroundColor Green
    Write-Host "      [OK] API Docs:    http://localhost:8000/docs" -ForegroundColor Green
} catch {
    Write-Host "      [WARN] API may still be starting..." -ForegroundColor Yellow
}
Pop-Location

# ── Step 4: Frontend ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] Starting React frontend on port 5173..." -ForegroundColor Yellow
Push-Location "$ROOT\frontend-app"

if (-not (Test-Path "node_modules")) {
    Write-Host "      Installing npm packages (first run ~2 minutes)..." -ForegroundColor Yellow
    npm install --legacy-peer-deps
}

$frontendJob = Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ROOT\frontend-app'; Write-Host 'CareLock Frontend' -ForegroundColor Cyan; npm run dev"
) -PassThru
Write-Host "      Waiting 8 seconds for frontend to compile..." -ForegroundColor Gray
Start-Sleep -Seconds 8
Pop-Location

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host "   CARELOCK SYNC IS READY FOR DEMO" -ForegroundColor Green
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "   Frontend:   http://localhost:5173" -ForegroundColor White
Write-Host "   API:        http://localhost:8000" -ForegroundColor White
Write-Host "   API Docs:   http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "   Login with: admin@carelock.demo  /  any-password" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Demo flow:" -ForegroundColor Yellow
Write-Host "     1. Login at http://localhost:5173/login" -ForegroundColor Gray
Write-Host "     2. Click 'Live Demo' in the sidebar" -ForegroundColor Gray
Write-Host "     3. Click 'Auto-play full demo'" -ForegroundColor Gray
Write-Host "     4. Explore all 6 pages" -ForegroundColor Gray
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host ""

# Open browser
Start-Sleep -Seconds 2
Start-Process "http://localhost:5173"

Write-Host "  Press Enter to STOP all services and exit..." -ForegroundColor Yellow
Read-Host

# Cleanup
Write-Host "  Stopping services..." -ForegroundColor Yellow
if ($backendJob)  { Stop-Process -Id $backendJob.Id  -Force -ErrorAction SilentlyContinue }
if ($frontendJob) { Stop-Process -Id $frontendJob.Id -Force -ErrorAction SilentlyContinue }
Set-Location $ROOT
docker compose -f docker-compose-demo.yml down 2>&1 | Out-Null
Write-Host "  All services stopped. Goodbye." -ForegroundColor Cyan
