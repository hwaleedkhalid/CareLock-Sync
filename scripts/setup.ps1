# CareLock Sync - Quick Setup Script for Windows
# Run this script to setup the complete system

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "CareLock Sync - Automated Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker
Write-Host "[1/10] Checking Docker..." -ForegroundColor Yellow
$dockerRunning = docker ps 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}
Write-Host "  Docker is running" -ForegroundColor Green

# Start Docker containers
Write-Host ""
Write-Host "[2/10] Starting Docker containers..." -ForegroundColor Yellow
cd docker
docker-compose -f docker-compose.dev.yml up -d
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Containers started successfully" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Failed to start containers" -ForegroundColor Red
    exit 1
}
cd ..

# Wait for databases
Write-Host ""
Write-Host "[3/10] Waiting for databases to initialize (15 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 15
Write-Host "  Databases should be ready" -ForegroundColor Green

# Create virtual environment
Write-Host ""
Write-Host "[4/10] Creating Python virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "  Virtual environment already exists" -ForegroundColor Green
} else {
    python -m venv venv
    Write-Host "  Virtual environment created" -ForegroundColor Green
}

# Install dependencies
Write-Host ""
Write-Host "[5/10] Installing Python dependencies..." -ForegroundColor Yellow
.\venv\Scripts\pip install -r backend/requirements.txt
Write-Host "  Dependencies installed" -ForegroundColor Green

# Initialize hospital database schema
Write-Host ""
Write-Host "[6/10] Initializing hospital database schema..." -ForegroundColor Yellow
Get-Content databases/hospital-dbs/01_schema.sql | docker exec -i carelock-hospital-db psql -U hospital_user -d hospital_db
Write-Host "  Hospital schema created" -ForegroundColor Green

# Generate test data
Write-Host ""
Write-Host "[7/10] Generating test data (500 patients)..." -ForegroundColor Yellow
.\venv\Scripts\python scripts/generate_hospital_data.py
Write-Host "  Test data generated" -ForegroundColor Green

# Initialize shared database schema
Write-Host ""
Write-Host "[8/10] Initializing shared FHIR database schema..." -ForegroundColor Yellow
Get-Content databases/shared-db/01_fhir_schema.sql | docker exec -i carelock-shared-db psql -U shared_user -d carelock_shared
Write-Host "  FHIR schema created" -ForegroundColor Green

# Setup CDC
Write-Host ""
Write-Host "[9/10] Setting up Change Data Capture..." -ForegroundColor Yellow
.\venv\Scripts\python backend/connector/cdc_monitor.py
Write-Host "  CDC configured" -ForegroundColor Green

# Run initial sync
Write-Host ""
Write-Host "[10/10] Running initial synchronization..." -ForegroundColor Yellow
.\venv\Scripts\python -c "import sys; sys.path.insert(0, 'backend'); from etl.pipeline import ETLPipeline; ETLPipeline(1).sync_all(limit=10)"
Write-Host "  Initial sync complete" -ForegroundColor Green

# Summary
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "SETUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Activate virtual environment:" -ForegroundColor White
Write-Host "     .\venv\Scripts\activate" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. Start the API server:" -ForegroundColor White
Write-Host "     cd backend\api" -ForegroundColor Cyan
Write-Host "     python main.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. Open browser to:" -ForegroundColor White
Write-Host "     http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access Points:" -ForegroundColor Yellow
Write-Host "  - API Docs:    http://localhost:8000/docs" -ForegroundColor White
Write-Host "  - pgAdmin:     http://localhost:5050" -ForegroundColor White
Write-Host "  - Health:      http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "Credentials:" -ForegroundColor Yellow
Write-Host "  - pgAdmin:     admin@carelock.com / admin123" -ForegroundColor White
Write-Host ""
