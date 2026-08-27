# ============================================================================
# CareLock Sync - Start All Services
# Starts Docker, Backend, and Frontend in separate windows
# ============================================================================

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Projects\CareLock-Sync"

function Write-Success { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Info { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Header { param($msg) Write-Host "`n========================================" -ForegroundColor Cyan; Write-Host "  $msg" -ForegroundColor Cyan; Write-Host "========================================" -ForegroundColor Cyan }

Write-Header "CARELOCK SYNC - STARTING ALL SERVICES"

# Start Docker containers
Write-Info "Starting Docker containers..."
Set-Location $ProjectRoot
docker-compose up -d
Write-Success "Docker containers started"

# Wait for databases to be ready
Write-Info "Waiting for databases to be ready (30 seconds)..."
Start-Sleep -Seconds 30

# Start Backend in new window
Write-Info "Starting Backend API in new window..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot\backend\api'; & '..\venv\Scripts\python.exe' main.py"
Write-Success "Backend API starting on http://localhost:8000"

# Wait a bit for backend to initialize
Start-Sleep -Seconds 5

# Start Frontend in new window (if it exists)
$frontendPath = "$ProjectRoot\frontend\carelock-admin"
if (Test-Path $frontendPath) {
    Write-Info "Starting Frontend UI in new window..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev"
    Write-Success "Frontend UI starting on http://localhost:3000"
} else {
    Write-Warning "Frontend not found at $frontendPath"
}

Write-Header "ALL SERVICES STARTED!"
Write-Host ""
Write-Success "Services are running in separate windows:"
Write-Host "  - Docker Containers: Background" -ForegroundColor Gray
Write-Host "  - Backend API: http://localhost:8000" -ForegroundColor Gray
Write-Host "  - API Docs: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "  - Frontend UI: http://localhost:3000" -ForegroundColor Gray
Write-Host ""
Write-Info "To stop services:"
Write-Host "  - Close the PowerShell windows for Backend/Frontend" -ForegroundColor Gray
Write-Host "  - Run: docker-compose down" -ForegroundColor Gray
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
