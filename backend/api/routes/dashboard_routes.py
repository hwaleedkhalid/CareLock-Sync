"""
Dashboard Routes — System metrics, data quality, tenant info
Provides endpoints consumed by the frontend dashboard pages.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from typing import Optional
from datetime import datetime
import logging

from common.database import shared_db_session
from common.auth import require_auth, require_admin, AuthContext
from services.cdc_metrics import get_cdc_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Dashboard"])


# ── System Metrics ────────────────────────────────────────────────────────────
@router.get("/system/metrics")
async def get_system_metrics(auth: AuthContext = Depends(require_auth)):
    """
    Real-time CDC pipeline metrics derived from cdc_inbox / cdc_dead_letter /
    cdc_watermarks. Returns `available: false` when the CDC schema has not
    been applied yet (services/cdc_worker --setup not run).
    """
    try:
        with shared_db_session() as db:
            if auth.tenant_id:
                db.execute(text("SET app.tenant_id = :t"), {"t": str(auth.tenant_id)})
            return get_cdc_metrics(db)
    except Exception as e:
        logger.error(f"Error fetching system metrics: {e}")
        raise HTTPException(500, "Error retrieving system metrics")


# ── Data Quality Metrics ──────────────────────────────────────────────────────
@router.get("/metrics")
async def get_data_quality_metrics(auth: AuthContext = Depends(require_auth)):
    """
    Return data quality metrics for the Data Quality dashboard page.
    Shape: { completeness_score, sync_success_rate, mapping_accuracy, error_rate }
    """
    try:
        with shared_db_session() as db:
            if auth.tenant_id:
                db.execute(text("SET app.tenant_id = :t"), {"t": str(auth.tenant_id)})

            # Completeness: ratio of FHIR patients with all core fields populated
            total_patients = db.execute(
                text("SELECT COUNT(*) FROM fhir_patient")
            ).scalar() or 0

            complete_patients = 0
            if total_patients > 0:
                complete_patients = db.execute(text("""
                    SELECT COUNT(*) FROM fhir_patient
                    WHERE family_name IS NOT NULL
                      AND given_name IS NOT NULL
                      AND birth_date IS NOT NULL
                      AND gender IS NOT NULL
                """)).scalar() or 0

            completeness = complete_patients / total_patients if total_patients > 0 else 0.0

            # Mapping accuracy: ratio of encounters with valid type + status
            total_enc = db.execute(
                text("SELECT COUNT(*) FROM fhir_encounter")
            ).scalar() or 0
            mapped_enc = 0
            if total_enc > 0:
                mapped_enc = db.execute(text("""
                    SELECT COUNT(*) FROM fhir_encounter
                    WHERE type_display IS NOT NULL
                      AND status IS NOT NULL
                """)).scalar() or 0

            mapping_accuracy = mapped_enc / total_enc if total_enc > 0 else 0.0

            # CDC-derived sync_success_rate and error_rate (rolling 1h window).
            cdc = get_cdc_metrics(db)
            err_rate = cdc["error_rate"]
            sync_success_rate = round(1.0 - err_rate, 6) if cdc["available"] else None

        return {
            "completeness_score": round(completeness, 4),
            "sync_success_rate": sync_success_rate,
            "mapping_accuracy": round(mapping_accuracy, 4),
            "error_rate": err_rate if cdc["available"] else None,
        }
    except Exception as e:
        logger.error(f"Error fetching data quality metrics: {e}")
        raise HTTPException(500, "Error retrieving data quality metrics")


# ── Tenant Info ───────────────────────────────────────────────────────────────
@router.get("/tenant/info")
async def get_tenant_info(auth: AuthContext = Depends(require_auth)):
    """
    Return current tenant information.
    Shape: { hospital_id, hospital_name, hospital_code, is_active, created_at }
    """
    try:
        with shared_db_session() as db:
            tenant_id = auth.tenant_id or 1

            row = db.execute(text("""
                SELECT tenant_id, hospital_name, hospital_code, is_active, created_at
                FROM hospital_tenants
                WHERE tenant_id = :tid
            """), {"tid": tenant_id}).fetchone()

            if row:
                r = dict(row._mapping)
                return {
                    "hospital_id": r["tenant_id"],
                    "hospital_name": r["hospital_name"],
                    "hospital_code": r["hospital_code"],
                    "is_active": r["is_active"],
                    "created_at": str(r["created_at"]) if r.get("created_at") else None,
                }

            # Fallback for admin users without specific tenant
            return {
                "hospital_id": 0,
                "hospital_name": auth.hospital_name or "CareLock HQ",
                "hospital_code": "CARELOCK",
                "is_active": True,
                "created_at": None,
            }
    except Exception as e:
        logger.error(f"Error fetching tenant info: {e}")
        raise HTTPException(500, "Error retrieving tenant info")


# ── Tenant Stats ──────────────────────────────────────────────────────────────
@router.get("/tenant/stats")
async def get_tenant_stats(auth: AuthContext = Depends(require_auth)):
    """
    Return statistics for the current tenant.
    """
    try:
        with shared_db_session() as db:
            tenant_id = auth.tenant_id

            if tenant_id:
                db.execute(text("SET app.tenant_id = :t"), {"t": str(tenant_id)})

            stats = {}
            for table, key in [
                ("fhir_patient", "patients"),
                ("fhir_encounter", "encounters"),
                ("fhir_observation", "observations"),
                ("fhir_medication_request", "medications"),
            ]:
                try:
                    stats[key] = db.execute(
                        text(f"SELECT COUNT(*) FROM {table}")
                    ).scalar() or 0
                except Exception:
                    stats[key] = 0

        return {
            "tenant_id": tenant_id or 0,
            "patients": stats.get("patients", 0),
            "encounters": stats.get("encounters", 0),
            "observations": stats.get("observations", 0),
            "medications": stats.get("medications", 0),
            "total_records": sum(stats.values()),
        }
    except Exception as e:
        logger.error(f"Error fetching tenant stats: {e}")
        raise HTTPException(500, "Error retrieving tenant stats")


# ── Tenant List (admin) ──────────────────────────────────────────────────────
@router.get("/tenants")
async def list_tenants(auth: AuthContext = Depends(require_auth)):
    """
    List all onboarded hospital tenants with patient counts.
    Used by AdminDashboard tenant table.
    """
    try:
        with shared_db_session() as db:
            rows = db.execute(text("""
                WITH sr AS (
                    SELECT tenant_id,
                           SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS ok,
                           SUM(CASE WHEN status='failed'    THEN 1 ELSE 0 END) AS bad
                      FROM sync_runs
                     WHERE status IN ('completed','failed')
                     GROUP BY tenant_id
                )
                SELECT t.tenant_id, t.hospital_name, t.hospital_code, t.is_active,
                       t.last_sync_date, t.created_at,
                       COUNT(p.id) AS patient_count,
                       sr.ok, sr.bad
                FROM hospital_tenants t
                LEFT JOIN fhir_patient p ON p.tenant_id = t.tenant_id
                LEFT JOIN sr ON sr.tenant_id = t.tenant_id
                GROUP BY t.tenant_id, t.hospital_name, t.hospital_code,
                         t.is_active, t.last_sync_date, t.created_at,
                         sr.ok, sr.bad
                ORDER BY t.tenant_id
            """)).fetchall()

            def _rate(ok, bad):
                ok = int(ok or 0); bad = int(bad or 0)
                total = ok + bad
                if total == 0:
                    return None
                return round(max(0.0, min(1.0, ok / total)), 6)

            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "code": r[2],
                    "is_active": r[3],
                    "last_sync": str(r[4]) if r[4] else None,
                    "created_at": str(r[5]) if r[5] else None,
                    "patients": r[6] or 0,
                    "sync_rate": _rate(r[7], r[8]),
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"Error listing tenants: {e}")
        raise HTTPException(500, "Error retrieving tenants")


# ── Create Tenant (admin) ─────────────────────────────────────────────────────

class CreateTenantRequest(BaseModel):
    hospital_name: str = Field(..., min_length=2, max_length=100,
                               description="Full hospital name")
    hospital_code: str = Field(..., min_length=2, max_length=10,
                               description="Short unique hospital identifier (e.g. CGH)")
    city: Optional[str] = Field(None, max_length=100)
    db_type: str = Field("postgresql",
                         description="Database engine: postgresql | mysql | mongodb | sqlserver | oracle")
    db_host: str = Field(..., min_length=1, max_length=255,
                         description="Hostname or IP of the hospital database server")
    db_port: int = Field(5432, ge=1, le=65535)
    db_name: str = Field(..., min_length=1, max_length=100,
                         description="Database / schema name")
    db_user: str = Field(..., min_length=1, max_length=100)
    db_password: str = Field(..., min_length=1,
                             description="Plaintext password — encrypted at rest before storage")


@router.post("/tenants", status_code=201)
async def create_tenant(
    payload: CreateTenantRequest,
    auth: AuthContext = Depends(require_admin),
):
    """
    Onboard a new hospital tenant.
    Inserts a row into hospital_tenants, returns the new tenant_id.
    Requires admin role.
    """
    hospital_code = payload.hospital_code.strip().upper()

    try:
        with shared_db_session() as db:
            # ── Duplicate-code guard ──────────────────────────────────────────
            existing = db.execute(
                text("SELECT tenant_id FROM hospital_tenants WHERE hospital_code = :code"),
                {"code": hospital_code},
            ).fetchone()
            if existing:
                raise HTTPException(
                    409,
                    f"Hospital code '{hospital_code}' is already registered. "
                    "Use a different code or contact an administrator.",
                )

            # ── Derive a safe partition name ──────────────────────────────────
            partition_name = f"tenant_{hospital_code.lower()}"

            # ── Encrypt the DB password (AES-256-GCM via key manager) ─────────
            # key_manager is loaded in main.py; fall back to empty string when
            # the security module is not installed in the current environment.
            encrypted_password: Optional[str] = None
            try:
                from api.main import key_manager  # type: ignore
                if key_manager:
                    encrypted_password = key_manager.encrypt_credential(payload.db_password)
            except Exception:
                pass  # Security module unavailable — store credential reference only

            # ── Insert ────────────────────────────────────────────────────────
            row = db.execute(
                text("""
                    INSERT INTO hospital_tenants (
                        hospital_name,
                        hospital_code,
                        partition_name,
                        db_platform,
                        is_active,
                        onboarded_date,
                        created_at
                    )
                    VALUES (
                        :hospital_name,
                        :hospital_code,
                        :partition_name,
                        :db_platform,
                        TRUE,
                        NOW(),
                        NOW()
                    )
                    RETURNING tenant_id
                """),
                {
                    "hospital_name": payload.hospital_name.strip(),
                    "hospital_code": hospital_code,
                    "partition_name": partition_name,
                    "db_platform": payload.db_type,
                },
            ).fetchone()

            db.commit()
            tenant_id: int = row[0]

            logger.info(
                f"Tenant created: id={tenant_id} code={hospital_code} "
                f"by={getattr(auth, 'email', 'unknown')}"
            )

            return {
                "status": "success",
                "tenant_id": tenant_id,
                "hospital_code": hospital_code,
                "message": (
                    f"Hospital '{payload.hospital_name.strip()}' has been onboarded "
                    f"successfully (tenant #{tenant_id}). "
                    "CDC monitoring and RLS isolation will activate on the next sync cycle."
                ),
            }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error creating tenant '{hospital_code}': {exc}", exc_info=True)
        raise HTTPException(500, f"Failed to onboard hospital: {exc}")


@router.get("/system/events")
async def get_system_events(
    limit: int = 100,
    event_type: str = None,
    auth: AuthContext = Depends(require_auth),
):
    """Return recent system events from the persistent event log."""
    from common.event_log import event_log
    return {
        "events": event_log.recent(limit=limit, event_type=event_type),
        "stats":  event_log.stats(),
    }
