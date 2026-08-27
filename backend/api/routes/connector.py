"""
Connector API Routes — Sprint 2 Complete
Adds: per-tenant health, all-DB connection check, schema export,
      observability views exposure, tenant listing, CDC tenant_id tracking
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import text
import sys, os

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, backend_dir)

from common.config import settings
from common.database import shared_db_session
from common.auth import require_auth, require_admin, AuthContext
from connector.schema_discovery import SchemaDiscovery
from connector.cdc_monitor import CDCMonitor

router = APIRouter(prefix="/api/v1/connector", tags=["connector"])

# ── Pydantic models ──────────────────────────────────────────────────────────

class TenantInfo(BaseModel):
    tenant_id: int
    hospital_name: str
    hospital_code: str
    partition_name: str
    db_platform: str
    is_active: bool
    onboarded_date: Optional[str]
    last_sync_date: Optional[str]

class DBHealthResult(BaseModel):
    name: str
    platform: str
    connected: bool
    latency_ms: Optional[float]
    error: Optional[str]

class ConnectorHealth(BaseModel):
    overall: str
    checked_at: str
    databases: List[DBHealthResult]
    central_db: Dict[str, Any]

# ── existing endpoints (kept) ────────────────────────────────────────────────

@router.get("/schema")
async def discover_schema(auth: AuthContext = Depends(require_admin)):
    """Discover and return hospital (PostgreSQL) database schema."""
    try:
        d = SchemaDiscovery(settings.hospital_db_url)
        return d.get_complete_schema()
    except Exception as e:
        raise HTTPException(500, f"Schema discovery failed: {e}")


@router.get("/schema/table/{table_name}")
async def get_table_schema(table_name: str, auth: AuthContext = Depends(require_admin)):
    try:
        d = SchemaDiscovery(settings.hospital_db_url)
        if table_name not in d.get_all_tables():
            raise HTTPException(404, f"Table '{table_name}' not found")
        return d.get_table_schema(table_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/schema/relationships")
async def get_relationships(auth: AuthContext = Depends(require_admin)):
    try:
        d = SchemaDiscovery(settings.hospital_db_url)
        rels = d.get_table_relationships()
        return {"total_relationships": sum(len(v) for v in rels.values()), "relationships": rels}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/cdc/changes")
async def get_changes(
    table_name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    auth: AuthContext = Depends(require_admin)
):
    try:
        m = CDCMonitor(settings.hospital_db_url)
        return m.get_recent_changes(table_name=table_name, limit=limit)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/cdc/statistics")
async def get_change_statistics(auth: AuthContext = Depends(require_admin)):
    try:
        m = CDCMonitor(settings.hospital_db_url)
        stats = m.get_change_statistics()
        return {"statistics": stats, "total_changes": sum(sum(v.values()) for v in stats.values())}
    except Exception as e:
        raise HTTPException(500, str(e))

# ── NEW Sprint 2 endpoints ───────────────────────────────────────────────────

@router.get("/tenants", response_model=List[TenantInfo])
async def list_tenants(active_only: bool = Query(False), auth: AuthContext = Depends(require_auth)):
    """List all onboarded hospitals with partition info."""
    try:
        with shared_db_session() as db:
            q = "SELECT tenant_id, hospital_name, hospital_code, partition_name, db_platform, is_active, onboarded_date, last_sync_date FROM hospital_tenants"
            if active_only:
                q += " WHERE is_active = TRUE"
            q += " ORDER BY tenant_id"
            rows = db.execute(text(q)).fetchall()
            return [
                {
                    "tenant_id":       r[0],
                    "hospital_name":   r[1],
                    "hospital_code":   r[2],
                    "partition_name":  r[3],
                    "db_platform":     r[4],
                    "is_active":       r[5],
                    "onboarded_date":  r[6].isoformat() if r[6] else None,
                    "last_sync_date":  r[7].isoformat() if r[7] else None,
                }
                for r in rows
            ]
    except Exception as e:
        raise HTTPException(500, f"Failed to list tenants: {e}")


@router.get("/tenants/{tenant_id}/health")
async def tenant_health(tenant_id: int, auth: AuthContext = Depends(require_auth)):
    """Per-tenant data quality and sync health from observability views."""
    try:
        with shared_db_session() as db:
            db.execute(text("SET app.tenant_id = :tid"), {"tid": str(tenant_id)})

            quality = db.execute(text(
                "SELECT * FROM v_tenant_health WHERE tenant_id = :tid"
            ), {"tid": tenant_id}).fetchone()

            partitions = db.execute(text(
                "SELECT * FROM v_partition_stats WHERE partition_name LIKE :pat"
            ), {"pat": f"%tenant_%"}).fetchall()

            cdc = db.execute(text(
                "SELECT * FROM v_cdc_lag WHERE tenant_id = :tid"
            ), {"tid": tenant_id}).fetchall()

            jsonb_keys = db.execute(text(
                "SELECT json_key, usage_count, recommendation FROM v_jsonb_promotion_candidates WHERE tenant_id = :tid LIMIT 20"
            ), {"tid": tenant_id}).fetchall()

            return {
                "tenant_id": tenant_id,
                "data_quality": dict(quality._mapping) if quality else None,
                "partition_stats": [dict(r._mapping) for r in partitions],
                "cdc_lag": [dict(r._mapping) for r in cdc],
                "jsonb_fields": [{"key": r[0], "usage": r[1], "recommendation": r[2]} for r in jsonb_keys],
                "checked_at": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        raise HTTPException(500, f"Tenant health check failed: {e}")


@router.get("/health", response_model=ConnectorHealth)
async def all_databases_health(auth: AuthContext = Depends(require_auth)):
    """Check connectivity to all configured database platforms."""
    import time
    from sqlalchemy import create_engine

    DB_CONFIGS = [
        {"name": "PostgreSQL Hospital", "platform": "postgresql", "url": settings.hospital_db_url},
        {"name": "Central FHIR",        "platform": "postgresql", "url": settings.shared_db_url},
    ]
    # Add other DBs if configured in settings
    for config_attr, name, platform in [
        ("MYSQL_URL",     "MySQL Hospital",      "mysql"),
        ("ORACLE_URL",    "Oracle Hospital",     "oracle"),
        ("SQLSERVER_URL", "SQL Server Hospital", "sqlserver"),
        ("MONGODB_URL",   "MongoDB Hospital",    "mongodb"),
    ]:
        url = getattr(settings, config_attr, None)
        if url:
            DB_CONFIGS.append({"name": name, "platform": platform, "url": url})

    def _normalise_url(url: str, platform: str) -> str:
        """Remap stale dialect names to currently-installed packages."""
        # oracle+cx_oracle → oracle+oracledb (cx_Oracle deprecated; oracledb is installed)
        if url.startswith("oracle+cx_oracle://"):
            url = "oracle+oracledb://" + url[len("oracle+cx_oracle://"):]
        # SQL Server: replace any missing ODBC driver with the first available one
        if platform == "sqlserver" and "driver=" in url.lower():
            try:
                import pyodbc
                available = pyodbc.drivers()
                preferred = next(
                    (d for d in ["ODBC Driver 18 for SQL Server",
                                 "ODBC Driver 17 for SQL Server",
                                 "SQL Server Native Client 11.0",
                                 "SQL Server"] if d in available),
                    None,
                )
                if preferred:
                    import re
                    url = re.sub(r"driver=[^&]+", f"driver={preferred.replace(' ', '+')}", url, flags=re.IGNORECASE)
                    # ODBC Driver 17/18 enforce TLS certificate validation by default;
                    # for local dev/Docker SQL Server add TrustServerCertificate=yes
                    if preferred in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"):
                        if "TrustServerCertificate" not in url:
                            url += "&TrustServerCertificate=yes"
            except ImportError:
                pass
        return url

    results = []
    for cfg in DB_CONFIGS:
        t0 = time.time()
        url = _normalise_url(cfg["url"], cfg["platform"])
        try:
            if cfg["platform"] == "mongodb":
                # MongoDB uses pymongo, not SQLAlchemy
                from pymongo import MongoClient
                client = MongoClient(url, serverSelectionTimeoutMS=3000)
                client.admin.command("ping")
                client.close()
            else:
                # PostgreSQL, MySQL, Oracle, SQL Server via SQLAlchemy
                connect_args = {"connect_timeout": 3}
                if cfg["platform"] == "oracle":
                    connect_args = {}  # oracledb thin mode handles timeouts internally
                eng = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
                with eng.connect() as conn:
                    # Oracle requires FROM DUAL; all others support bare SELECT 1
                    if cfg["platform"] == "oracle":
                        conn.execute(text("SELECT 1 FROM DUAL"))
                    else:
                        conn.execute(text("SELECT 1"))
                eng.dispose()
            latency = round((time.time() - t0) * 1000, 1)
            results.append({"name": cfg["name"], "platform": cfg["platform"],
                             "connected": True, "latency_ms": latency, "error": None})
        except Exception as ex:
            results.append({"name": cfg["name"], "platform": cfg["platform"],
                             "connected": False, "latency_ms": None, "error": str(ex)[:120]})

    all_ok = all(r["connected"] for r in results)

    # Central DB stats
    central_stats = {}
    try:
        with shared_db_session() as db:
            for tbl in ("fhir_patient", "fhir_encounter", "fhir_observation", "fhir_medication_request"):
                central_stats[tbl] = db.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
    except Exception:
        pass

    return {
        "overall": "healthy" if all_ok else "degraded",
        "checked_at": datetime.utcnow().isoformat(),
        "databases": results,
        "central_db": central_stats,
    }


@router.get("/observability/partitions")
async def partition_stats(auth: AuthContext = Depends(require_auth)):
    """Partition sizes, dead rows and vacuum status for all FHIR tables."""
    try:
        with shared_db_session() as db:
            rows = db.execute(text("SELECT * FROM v_partition_stats")).fetchall()
            return [dict(r._mapping) for r in rows]
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/observability/cdc-lag")
async def cdc_lag(auth: AuthContext = Depends(require_auth)):
    """CDC backlog per tenant — includes lag_seconds and health alert status."""
    try:
        with shared_db_session() as db:
            rows = db.execute(text("SELECT * FROM v_cdc_lag")).fetchall()
            return [dict(r._mapping) for r in rows]
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/observability/index-health")
async def index_health(auth: AuthContext = Depends(require_auth)):
    """Index usage — flags UNUSED indexes that waste RAM."""
    try:
        with shared_db_session() as db:
            rows = db.execute(text("SELECT * FROM v_index_health")).fetchall()
            return [dict(r._mapping) for r in rows]
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/observability/jsonb-catalog")
async def jsonb_catalog(tenant_id: Optional[int] = Query(None)):
    """JSONB field catalog — shows which optional_data keys to promote to typed columns."""
    try:
        with shared_db_session() as db:
            q = "SELECT * FROM v_jsonb_promotion_candidates"
            params: Dict = {}
            if tenant_id:
                q += " WHERE tenant_id = :tid"
                params["tid"] = tenant_id
            rows = db.execute(text(q), params).fetchall()
            return [dict(r._mapping) for r in rows]
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/status")
async def connector_status(auth: AuthContext = Depends(require_auth)):
    """Quick connector status — CDC enabled, monitored tables, last change."""
    try:
        m = CDCMonitor(settings.hospital_db_url)
        try:
            changes = m.get_recent_changes(limit=1)
            cdc_enabled = True
            last_change = changes[0]['changed_at'] if changes else None
        except Exception:
            cdc_enabled = False
            last_change = None

        with shared_db_session() as db:
            tenant_count = db.execute(
                text("SELECT COUNT(*) FROM hospital_tenants WHERE is_active = TRUE")
            ).scalar()

        return {
            "status": "operational",
            "cdc_enabled": cdc_enabled,
            "monitored_tables": ["patients", "encounters", "lab_results", "medications"],
            "active_tenants": tenant_count,
            "schema_discovered": True,
            "last_cdc_event": last_change,
            "checked_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(500, str(e))
