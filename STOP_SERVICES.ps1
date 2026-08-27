# ============================================================================
# CareLock Sync - Stop All Services
# Stops Docker containers and closes service windows
# ============================================================================

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Projects\CareLock-Sync"

function Write-Success { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Info { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Header { param($msg) Write-Host "`n========================================" -ForegroundColor Cyan; Write-Host "  $msg" -ForegroundColor Cyan; Write-Host "========================================" -ForegroundColor Cyan }

Write-Header "CARELOCK SYNC - STOPPING ALL SERVICES"

# Stop Docker containers
Write-Info "Stopping Docker containers..."
Set-Location $ProjectRoot
docker-compose down
Write-Success "Docker containers stopped"

# Kill Python processes (backend)
Write-Info "Stopping backend processes..."
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    $pythonProcesses | Stop-Process -Force
    Write-Success "Backend processes stopped"
} else {
    Write-Info "No backend processes found"
}

# Kill Node processes (frontend)
Write-Info "Stopping frontend processes..."
$nodeProcesses = Get-Process node -ErrorAction SilentlyContinue
if ($nodeProcesses) {
    $nodeProcesses | Stop-Process -Force
    Write-Success "Frontend processes stopped"
} else {
    Write-Info "No frontend processes found"
}

Write-Header "ALL SERVICES STOPPED!"
Write-Success "All CareLock Sync services have been stopped"
Write-Host ""
Write-Host "To restart services, run: .\START_SERVICES.ps1" -ForegroundColor Gray
Write-Host ""
