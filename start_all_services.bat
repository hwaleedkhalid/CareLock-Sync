@echo off
REM CareLock — Start all backend services
REM Run this from the project root directory.

cd /d "%~dp0backend"

echo [1/4] Starting API Server (port 8003)...
start "CareLock API" cmd /k "set HOSPITAL_DB_URL=postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db && set SHARED_DB_URL=postgresql://shared_user:shared_pass@localhost:5433/carelock_shared && python run_server.py"

timeout /t 3 /nobreak >nul

echo [2/4] Starting CDC Ingestion Service (port 8004)...
start "CareLock Ingestion" cmd /k "set HOSPITAL_DB_URL=postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db && set SHARED_DB_URL=postgresql://shared_user:shared_pass@localhost:5433/carelock_shared && set CDC_HMAC_KEYS=hospital_a:carelock-cdc-2024 && set LOG_LEVEL=INFO && python -m uvicorn services.ingestion.app:app --host 0.0.0.0 --port 8004 --log-level info"

timeout /t 3 /nobreak >nul

echo [3/4] Starting CDC Worker (hospital_a)...
start "CareLock CDC Worker" cmd /k "set HOSPITAL_DB_URL=postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db && set SHARED_DB_URL=postgresql://shared_user:shared_pass@localhost:5433/carelock_shared && set CDC_HMAC_KEY_HOSPITAL_A=carelock-cdc-2024 && set CDC_REGISTRY_AUTO_STUB=true && set LOG_LEVEL=INFO && python -m services.cdc_worker --source hospital_a"

timeout /t 2 /nobreak >nul

echo [4/4] Starting ETL Worker...
start "CareLock ETL Worker" cmd /k "set HOSPITAL_DB_URL=postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db && set SHARED_DB_URL=postgresql://shared_user:shared_pass@localhost:5433/carelock_shared && set LOG_LEVEL=INFO && python -m services.etl_worker"

echo.
echo All services started. Check the console windows for logs.
echo.
echo Service endpoints:
echo   API Server    : http://localhost:8003
echo   Ingestion     : http://localhost:8004/healthz
echo   CDC Worker    : http://localhost:9101/status  (admin)
echo   ETL Worker    : http://localhost:9201/status  (admin)
pause
