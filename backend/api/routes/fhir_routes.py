"""
FHIR Routes — Encounters + Dashboard Stats (tenant-isolated)

Queries the shared FHIR central DB via raw SQL (same pattern as sync.py
and patients.py /fhir/ endpoint).

Patient routes live in patients.py.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from typing import Optional
import logging

from common.database import shared_db_session
from common.auth import require_auth, AuthContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["FHIR"])


# ── Encounters ────────────────────────────────────────────────────────────────
@router.get("/encounters")
async def get_encounters(
    patient_id: Optional[int] = Query(None),
    auth: AuthContext = Depends(require_auth),
):
    """
    Tenant-isolated encounter list from FHIR central DB.
    Returns a flat array of Encounter objects (matches frontend Encounter[] type).
    """
    try:
        with shared_db_session() as db:
            if auth.tenant_id:
                db.execute(text("SET app.tenant_id = :t"), {"t": str(auth.tenant_id)})

            params: dict = {}
            sql = """
                SELECT id, tenant_id, patient_id,
                       source_encounter_id, type_display,
                       period_start, period_end, status
                FROM fhir_encounter
            """
            if patient_id:
                sql += " WHERE patient_id = :pid"
                params["pid"] = patient_id
            sql += " ORDER BY id"

            rows = db.execute(text(sql), params).fetchall()

            return [
                {
                    "id": r[0],
                    "tenant_id": r[1],
                    "patient_id": r[2],
                    "encounter_id": str(r[3]) if r[3] else None,
                    "encounter_type": r[4] or "Unknown",
                    "start_date": str(r[5]) if r[5] else None,
                    "end_date": str(r[6]) if r[6] else None,
                    "status": r[7] or "unknown",
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"Error fetching encounters: {e}")
        raise HTTPException(500, "Error retrieving encounters")


# ── Dashboard Stats ───────────────────────────────────────────────────────────
@router.get("/stats")
async def get_stats(auth: AuthContext = Depends(require_auth)):
    """
    Dashboard KPIs — record counts from FHIR central DB.
    Tenant-isolated: hospital roles see only their own data.
    Field names match the frontend DashboardStats type:
        { total_patients, total_encounters, total_observations, total_medications }
    """
    try:
        with shared_db_session() as db:
            if auth.tenant_id:
                db.execute(text("SET app.tenant_id = :t"), {"t": str(auth.tenant_id)})

            counts = {}
            for table in ("fhir_patient", "fhir_encounter",
                          "fhir_observation", "fhir_medication_request"):
                try:
                    counts[table] = db.execute(
                        text(f"SELECT COUNT(*) FROM {table}")
                    ).scalar() or 0
                except Exception:
                    counts[table] = 0

            return {
                "total_patients":     counts["fhir_patient"],
                "total_encounters":   counts["fhir_encounter"],
                "total_observations": counts["fhir_observation"],
                "total_medications":  counts["fhir_medication_request"],
            }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(500, "Error retrieving statistics")


# ── Observations ──────────────────────────────────────────────────────────────
@router.get("/observations")
async def get_observations(
    patient_id: Optional[int] = Query(None),
    auth: AuthContext = Depends(require_auth),
):
    """
    Tenant-isolated observation list from FHIR central DB.
    """
    try:
        with shared_db_session() as db:
            if auth.tenant_id:
                db.execute(text("SET app.tenant_id = :t"), {"t": str(auth.tenant_id)})

            params: dict = {}
            sql = """
                SELECT id, tenant_id, patient_id,
                       code_display, value_quantity_value, value_quantity_unit,
                       value_string, effective_datetime, status
                FROM fhir_observation
            """
            if patient_id:
                sql += " WHERE patient_id = :pid"
                params["pid"] = patient_id
            sql += " ORDER BY effective_datetime DESC NULLS LAST, id"

            rows = db.execute(text(sql), params).fetchall()

            return [
                {
                    "id": r[0],
                    "tenant_id": r[1],
                    "patient_id": r[2],
                    "code": r[3] or "Unknown",
                    "value": f"{float(r[4])} {r[5]}" if r[4] is not None else (r[6] or "N/A"),
                    "date": str(r[7]) if r[7] else None,
                    "status": r[8] or "final",
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"Error fetching observations: {e}")
        raise HTTPException(500, "Error retrieving observations")


# ── Medication Requests ───────────────────────────────────────────────────────
@router.get("/medications")
async def get_medications(
    patient_id: Optional[int] = Query(None),
    auth: AuthContext = Depends(require_auth),
):
    """
    Tenant-isolated medication request list from FHIR central DB.
    """
    try:
        with shared_db_session() as db:
            if auth.tenant_id:
                db.execute(text("SET app.tenant_id = :t"), {"t": str(auth.tenant_id)})

            params: dict = {}
            sql = """
                SELECT id, tenant_id, patient_id,
                       medication_code_display, dosage_text,
                       authored_on, status
                FROM fhir_medication_request
            """
            if patient_id:
                sql += " WHERE patient_id = :pid"
                params["pid"] = patient_id
            sql += " ORDER BY authored_on DESC NULLS LAST, id"

            rows = db.execute(text(sql), params).fetchall()

            return [
                {
                    "id": r[0],
                    "tenant_id": r[1],
                    "patient_id": r[2],
                    "name": r[3] or "Unknown medication",
                    "dosage": r[4] or "As directed",
                    "prescribed": str(r[5]) if r[5] else None,
                    "status": r[6] or "active",
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"Error fetching medications: {e}")
        raise HTTPException(500, "Error retrieving medications")
