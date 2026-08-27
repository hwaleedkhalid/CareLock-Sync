"""
API routes for database and system status.
Returns real measured values for every field — no hardcoded defaults.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import time
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.database import get_hospital_db, get_shared_db
from common.schemas  import DatabaseStatus, SystemStatus
from common.models   import Patient, Encounter, LabResult, Medication
from common.auth     import require_auth, AuthContext

router = APIRouter(
    prefix="/api/v1/status",
    tags=["status"]
)

# Module-level start time — used to report real process uptime
_SERVER_START = time.time()


def _measure_db(db: Session, queries: list[tuple[str, str]]) -> dict:
    """
    Run a ping + optional count queries on a SQLAlchemy session.
    Returns connected=True, latency_ms=<measured ping ms>, and all count values.
    Latency is the wall-clock time for `SELECT 1` only (excludes count queries).
    """
    result = {"connected": False, "latency_ms": None}

    # ── Ping ────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        result["connected"] = True
    except Exception:
        return result

    # ── Count queries (best-effort, don't affect connected/latency) ──────────
    for key, sql in queries:
        try:
            result[key] = db.execute(text(sql)).scalar() or 0
        except Exception:
            result[key] = None

    return result


@router.get("/database/hospital", response_model=DatabaseStatus)
async def hospital_database_status(
    db:   Session      = Depends(get_hospital_db),
    auth: AuthContext  = Depends(require_auth)
):
    """Hospital database status with real measured latency."""
    data = _measure_db(db, [
        ("total_patients",    "SELECT COUNT(*) FROM patients"),
        ("total_encounters",  "SELECT COUNT(*) FROM encounters"),
        ("total_lab_results", "SELECT COUNT(*) FROM lab_results"),
        ("total_medications", "SELECT COUNT(*) FROM medications"),
    ])
    return {
        "database_name":    "hospital_db",
        "connected":        data["connected"],
        "latency_ms":       data.get("latency_ms"),
        "total_patients":   data.get("total_patients"),
        "total_encounters": data.get("total_encounters"),
        "total_lab_results": data.get("total_lab_results"),
        "total_medications": data.get("total_medications"),
        "last_checked":     datetime.utcnow(),
    }


@router.get("/database/shared", response_model=DatabaseStatus)
async def shared_database_status(
    db:   Session      = Depends(get_shared_db),
    auth: AuthContext  = Depends(require_auth)
):
    """Shared FHIR database status with real measured latency."""
    data = _measure_db(db, [
        ("total_patients",    "SELECT COUNT(*) FROM fhir_patient"),
        ("total_encounters",  "SELECT COUNT(*) FROM fhir_encounter"),
        ("total_lab_results", "SELECT COUNT(*) FROM fhir_observation"),
        ("total_medications", "SELECT COUNT(*) FROM fhir_medication_request"),
    ])
    return {
        "database_name":    "carelock_shared",
        "connected":        data["connected"],
        "latency_ms":       data.get("latency_ms"),
        "total_patients":   data.get("total_patients"),
        "total_encounters": data.get("total_encounters"),
        "total_lab_results": data.get("total_lab_results"),
        "total_medications": data.get("total_medications"),
        "last_checked":     datetime.utcnow(),
    }


@router.get("/system", response_model=SystemStatus)
async def system_status(
    hospital_db: Session      = Depends(get_hospital_db),
    shared_db:   Session      = Depends(get_shared_db),
    auth:        AuthContext   = Depends(require_auth)
):
    """
    Overall system status.
    uptime_seconds  — real process uptime since server start.
    latency_ms      — real measured SELECT 1 round-trip per database.
    """
    hospital_data = _measure_db(hospital_db, [
        ("total_patients",    "SELECT COUNT(*) FROM patients"),
        ("total_encounters",  "SELECT COUNT(*) FROM encounters"),
        ("total_lab_results", "SELECT COUNT(*) FROM lab_results"),
        ("total_medications", "SELECT COUNT(*) FROM medications"),
    ])
    shared_data = _measure_db(shared_db, [
        ("total_patients",    "SELECT COUNT(*) FROM fhir_patient"),
        ("total_encounters",  "SELECT COUNT(*) FROM fhir_encounter"),
        ("total_lab_results", "SELECT COUNT(*) FROM fhir_observation"),
        ("total_medications", "SELECT COUNT(*) FROM fhir_medication_request"),
    ])

    hospital_status = {
        "database_name":    "hospital_db",
        "connected":        hospital_data["connected"],
        "latency_ms":       hospital_data.get("latency_ms"),
        "total_patients":   hospital_data.get("total_patients"),
        "total_encounters": hospital_data.get("total_encounters"),
        "total_lab_results": hospital_data.get("total_lab_results"),
        "total_medications": hospital_data.get("total_medications"),
        "last_checked":     datetime.utcnow(),
    }
    shared_status = {
        "database_name":    "carelock_shared",
        "connected":        shared_data["connected"],
        "latency_ms":       shared_data.get("latency_ms"),
        "total_patients":   shared_data.get("total_patients"),
        "total_encounters": shared_data.get("total_encounters"),
        "total_lab_results": shared_data.get("total_lab_results"),
        "total_medications": shared_data.get("total_medications"),
        "last_checked":     datetime.utcnow(),
    }

    return {
        "api_status":      "running",
        "uptime_seconds":  round(time.time() - _SERVER_START, 1),
        "hospital_db":     hospital_status,
        "shared_db":       shared_status,
        "timestamp":       datetime.utcnow(),
    }
