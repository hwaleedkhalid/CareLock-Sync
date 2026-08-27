"""
Sync API — production-grade.

State is persisted in the shared DB table `sync_runs` (see sync_store.py).
Every run has a UUID sync_id, status lifecycle (queued → running → completed/failed),
live progress (0-100), current_step, and records_processed JSON.

Concurrency: an active (queued|running) run blocks new triggers for the same
tenant. Scheduler uses the same lock.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, status
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import json, math, time, logging, sys, os
from concurrent.futures import ThreadPoolExecutor, wait as cf_wait

current_dir = os.path.dirname(os.path.abspath(__file__))
api_dir     = os.path.dirname(current_dir)
backend_dir = os.path.dirname(api_dir)
sys.path.insert(0, backend_dir)

etl_path = os.path.join(backend_dir, 'etl')
sys.path.insert(0, etl_path)

from pipeline          import ETLPipeline
from incremental_sync  import IncrementalSync
from common.database   import shared_db_session
from common.auth       import require_auth, require_admin, require_write, AuthContext
from common.event_log  import event_log
from common            import sync_store
from sqlalchemy        import text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sync", tags=["sync"])

# ── Pydantic models ──────────────────────────────────────────────────────────
class SyncRequest(BaseModel):
    tenant_id: int = 1
    limit: Optional[int] = None
    mode: Optional[str] = None     # "full" | "incremental" | None (auto)

class IncrementalSyncRequest(BaseModel):
    tenant_id: int = 1
    last_sync_id: Optional[int] = None


# ── helpers ──────────────────────────────────────────────────────────────────
def _resolve_tenant(request_tenant: int, auth: AuthContext) -> int:
    if auth.role == "hospital":
        if request_tenant != auth.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your account is scoped to tenant {auth.tenant_id}, "
                       f"cannot sync tenant {request_tenant}"
            )
        return auth.tenant_id
    return request_tenant


def _classify_error(exc: Exception) -> tuple[int, str]:
    msg = str(exc); lower = msg.lower()
    if any(k in lower for k in ('connection', 'could not connect', 'authentication failed',
                                'operational error', 'psycopg2', 'timeout')):
        return 503, ("Database unreachable. Ensure the hospital and shared databases are running "
                     "and credentials in config/.env are correct.")
    return 500, f"Sync failed unexpectedly: {msg}"


def _make_progress_cb(sync_id: str):
    """Return a progress callback for ETLPipeline that persists updates."""
    def cb(step: str, progress: int, records: Dict[str, Any]) -> None:
        sync_store.update_progress(sync_id,
                                    progress=progress,
                                    current_step=step,
                                    records_processed=records)
    return cb


# ── Background task bodies ────────────────────────────────────────────────────
def _run_full_sync(tenant_id: int, sync_id: str, triggered_by: str,
                   limit: Optional[int]) -> None:
    try:
        logger.info(f"[{sync_id}] Full sync started for tenant {tenant_id} by {triggered_by}")
        sync_store.start_run(sync_id, current_step="patients")

        pipeline = ETLPipeline(tenant_id=tenant_id, progress_cb=_make_progress_cb(sync_id))
        stats = pipeline.sync_all(limit=limit)

        records = {k: v.get('loaded', 0) for k, v in stats.items()}
        sync_store.complete_run(sync_id, records_processed=records)
        event_log.write('SYNC_COMPLETED', triggered_by, tenant_id,
                        f"Full sync {sync_id} completed", records)
        logger.info(f"[{sync_id}] Full sync completed: {records}")
    except Exception as exc:
        sync_store.fail_run(sync_id, str(exc))
        http_code, _ = _classify_error(exc)
        event_log.write('SYNC_FAILED', triggered_by, tenant_id,
                        f"Full sync {sync_id} failed ({http_code})", {'error': str(exc)})
        logger.error(f"[{sync_id}] Full sync failed: {exc}", exc_info=True)


def _run_incremental_sync(tenant_id: int, sync_id: str, triggered_by: str,
                          last_sync_id: Optional[int]) -> None:
    try:
        logger.info(f"[{sync_id}] Incremental sync started for tenant {tenant_id}")
        sync_store.start_run(sync_id, current_step="cdc")
        sync_store.update_progress(sync_id, progress=10, current_step="reading CDC log")

        stats = IncrementalSync(tenant_id=tenant_id).sync_incremental(last_sync_id)
        records = {
            'changes_applied': stats.get('synced', 0),
            'errors':          stats.get('errors', 0),
            'by_table':        stats.get('by_table', {}),
        }
        sync_store.update_progress(sync_id, progress=95, current_step="finalising",
                                    last_checkpoint=stats.get('last_change_id'))
        sync_store.complete_run(sync_id, records_processed=records)
        event_log.write('SYNC_COMPLETED', triggered_by, tenant_id,
                        f"Incremental sync {sync_id} completed", records)
        logger.info(f"[{sync_id}] Incremental sync completed: {records}")
    except Exception as exc:
        sync_store.fail_run(sync_id, str(exc))
        event_log.write('SYNC_FAILED', triggered_by, tenant_id,
                        f"Incremental sync {sync_id} failed", {'error': str(exc)})
        logger.error(f"[{sync_id}] Incremental sync failed: {exc}", exc_info=True)


def _pick_mode(tenant_id: int, requested: Optional[str]) -> str:
    """Auto-select mode: first run → full, subsequent → incremental."""
    if requested in ('full', 'incremental'):
        return requested
    latest = sync_store.get_latest_run(tenant_id)
    if latest is None or latest.get('status') != 'completed':
        return 'full'
    return 'incremental'


# ── Sync endpoints ────────────────────────────────────────────────────────────
@router.post("/full", status_code=202)
async def trigger_full_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(require_write),
):
    """
    Queue a sync run. Returns 202 with sync_id immediately.
    Client polls GET /api/v1/sync/status?sync_id=... for progress.

    Mode selection:
      - request.mode == 'full'        → force full reload
      - request.mode == 'incremental' → force CDC-driven incremental
      - request.mode is None          → auto (incremental after first success)
    """
    tenant_id = _resolve_tenant(request.tenant_id, auth)
    auth.assert_tenant(tenant_id)

    mode = _pick_mode(tenant_id, request.mode)

    # Atomic: pg_advisory_xact_lock + reap zombies + check active + insert.
    sync_id, conflicting, reaped = sync_store.trigger_atomic(
        tenant_id, sync_type=mode, triggered_by=auth.email,
    )
    if reaped:
        event_log.write('SYNC_REAPED', auth.email, tenant_id,
                        f"Reaped {reaped} stale sync run(s) before triggering",
                        {'reaped': reaped})
    if conflicting is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Sync {conflicting['sync_id']} is already {conflicting['status']}. "
                   f"Wait for it to finish or poll /api/v1/sync/status.",
        )

    event_log.write('SYNC_TRIGGERED', auth.email, tenant_id,
                    f"{mode.capitalize()} sync {sync_id} triggered",
                    {'mode': mode, 'triggered_by': auth.email})

    if mode == 'full':
        background_tasks.add_task(_run_full_sync, tenant_id, sync_id, auth.email, request.limit)
    else:
        background_tasks.add_task(_run_incremental_sync, tenant_id, sync_id, auth.email, None)

    return {
        "status":       "queued",
        "message":      f"{mode.capitalize()} sync queued.",
        "sync_id":      sync_id,
        "mode":         mode,
        "tenant_id":    tenant_id,
        "triggered_by": auth.email,
    }


@router.post("/incremental", status_code=202)
async def trigger_incremental_sync(
    request: IncrementalSyncRequest,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(require_write),
):
    """Queue an incremental CDC sync explicitly."""
    tenant_id = _resolve_tenant(request.tenant_id, auth)
    auth.assert_tenant(tenant_id)

    sync_id, conflicting, reaped = sync_store.trigger_atomic(
        tenant_id, sync_type='incremental', triggered_by=auth.email,
    )
    if reaped:
        event_log.write('SYNC_REAPED', auth.email, tenant_id,
                        f"Reaped {reaped} stale sync run(s) before triggering",
                        {'reaped': reaped})
    if conflicting is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Sync {conflicting['sync_id']} is already {conflicting['status']}.",
        )

    event_log.write('SYNC_TRIGGERED', auth.email, tenant_id,
                    f"Incremental sync {sync_id} triggered", {})

    background_tasks.add_task(_run_incremental_sync, tenant_id, sync_id,
                              auth.email, request.last_sync_id)

    return {
        "status":  "queued",
        "message": "Incremental sync queued.",
        "sync_id": sync_id,
        "mode":    "incremental",
        "tenant_id": tenant_id,
        "triggered_by": auth.email,
    }


# ── Read-only endpoints ───────────────────────────────────────────────────────
def _shape_status(run: Optional[Dict[str, Any]], total: int,
                  last_completed: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalise a run row into the shape the frontend expects."""
    stale_threshold_s = sync_store.STALE_AFTER_MINUTES * 60
    if run is None:
        return {
            "is_syncing":      False,
            "sync_id":         None,
            "status":          "idle",
            "progress":        0,
            "current_step":    None,
            "records_processed": {},
            "mode":            None,
            "started_at":      None,
            "completed_at":    last_completed['completed_at'] if last_completed else None,
            "duration_s":      None,
            "duration_seconds": None,
            "error":           None,
            "last_sync_time":  last_completed['completed_at'] if last_completed else None,
            "last_sync_stats": last_completed['records_processed'] if last_completed else None,
            "total_syncs":     total,
            "last_heartbeat_at": None,
            "is_stale":        False,
            "stale_threshold_seconds": stale_threshold_s,
        }

    is_syncing = run['status'] in ('queued', 'running')
    # duration in seconds (live for running, final for completed)
    dur = None
    if run.get('started_at'):
        end = run.get('completed_at') or datetime.utcnow().isoformat()
        try:
            dur = round(
                (datetime.fromisoformat(end) - datetime.fromisoformat(run['started_at']))
                .total_seconds(), 2
            )
        except Exception:
            dur = None

    # Fall back to last completed run for "last sync" panel while a new one runs
    last_src = last_completed if is_syncing and last_completed else run
    return {
        "is_syncing":        is_syncing,
        "sync_id":           run['sync_id'],
        "status":            run['status'],
        "progress":          run.get('progress', 0),
        "current_step":      run.get('current_step'),
        "records_processed": run.get('records_processed') or {},
        "mode":              run.get('sync_type'),
        "started_at":        run.get('started_at'),
        "completed_at":      run.get('completed_at'),
        "duration_s":        dur,
        "duration_seconds":  dur,
        "error":             run.get('error_message'),
        "last_sync_time":    last_src.get('completed_at') if last_src else None,
        "last_sync_stats":   last_src.get('records_processed') if last_src else None,
        "total_syncs":       total,
        "last_heartbeat_at": run.get('updated_at'),
        "is_stale":          sync_store.is_stale_run(run),
        "stale_threshold_seconds": stale_threshold_s,
    }


@router.get("/status")
async def get_sync_status(
    sync_id: Optional[str] = None,
    tenant_id: Optional[int] = None,
    auth: AuthContext = Depends(require_auth),
):
    """Return status of a specific sync (via sync_id) or the latest run."""
    # Scope: hospital users see only their tenant
    scope_tenant = auth.tenant_id if auth.role == "hospital" else tenant_id

    if sync_id:
        run = sync_store.get_run(sync_id)
        if run and scope_tenant is not None and run['tenant_id'] != scope_tenant:
            raise HTTPException(403, "Sync belongs to another tenant.")
    else:
        # Prefer an active run, else most recent run
        run = (sync_store.get_active_run(scope_tenant)
               or sync_store.get_latest_run(scope_tenant))

    total = sync_store.total_syncs(scope_tenant)

    # Always surface the last completed run so UI can show "last sync" while running
    last_completed = None
    for r in sync_store.list_runs(scope_tenant, limit=10):
        if r['status'] == 'completed':
            last_completed = r
            break

    return _shape_status(run, total, last_completed)


@router.get("/history")
async def get_sync_history(limit: int = 10, auth: AuthContext = Depends(require_auth)):
    scope_tenant = auth.tenant_id if auth.role == "hospital" else None
    runs = sync_store.list_runs(scope_tenant, limit=limit)
    return {
        "total":   len(runs),
        "limit":   limit,
        "history": [{
            'sync_id':      r['sync_id'],
            'type':         r['sync_type'],
            'status':       r['status'],
            'started_at':   r['started_at'],
            'completed_at': r['completed_at'],
            'stats':        r['records_processed'],
            'error':        r.get('error_message'),
            'duration_s':   (
                round(
                    (datetime.fromisoformat(r['completed_at']) - datetime.fromisoformat(r['started_at']))
                    .total_seconds(), 2)
                if r.get('started_at') and r.get('completed_at') else None
            ),
        } for r in runs],
    }


@router.get("/statistics")
async def get_sync_statistics(auth: AuthContext = Depends(require_auth)):
    try:
        with shared_db_session() as db:
            if auth.role == "hospital":
                db.execute(text("SET app.tenant_id = :t"), {"t": str(auth.tenant_id)})
            counts = {
                t: db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() or 0
                for t in ("fhir_patient", "fhir_encounter",
                          "fhir_observation", "fhir_medication_request")
            }
            tenant = db.execute(text(
                "SELECT hospital_name, hospital_code FROM hospital_tenants WHERE tenant_id=:t"
            ), {"t": auth.tenant_id or 1}).fetchone()

        scope_tenant = auth.tenant_id if auth.role == "hospital" else None
        latest = sync_store.get_latest_run(scope_tenant)
        active = sync_store.get_active_run(scope_tenant)

        return {
            "tenant": {"name": tenant[0] if tenant else None,
                       "code": tenant[1] if tenant else None},
            "fhir_resources": {**counts, "total": sum(counts.values())},
            "sync_state": {
                "is_syncing":     active is not None,
                "total_syncs":    sync_store.total_syncs(scope_tenant),
                "last_sync_time": latest['completed_at'] if latest else None,
                "last_sync_id":   latest['sync_id'] if latest else None,
                "last_sync_mode": latest['sync_type'] if latest else None,
            },
        }
    except Exception as exc:
        http_code, msg = _classify_error(exc)
        raise HTTPException(http_code, msg)


# ── Admin-only ────────────────────────────────────────────────────────────────
@router.delete("/reset")
async def reset_sync_state(auth: AuthContext = Depends(require_admin)):
    """Reap any stuck runs (doesn't delete history, just unblocks new triggers)."""
    reaped = sync_store.reap_stuck_runs(older_than_minutes=0)
    event_log.write('SYNC_RESET', auth.email, None,
                    f"Sync state reset — reaped {reaped} stuck runs", {'reaped': reaped})
    return {"status": "success", "reaped": reaped, "by": auth.email}


# ── Observability ─────────────────────────────────────────────────────────────
@router.get("/health")
async def sync_health(auth: AuthContext = Depends(require_auth)):
    try:
        with shared_db_session() as db:
            rows = db.execute(text("SELECT * FROM v_cdc_lag")).fetchall()
        return {"cdc_lag": [dict(r._mapping) for r in rows],
                "checked_at": datetime.utcnow().isoformat()}
    except Exception as exc:
        http_code, msg = _classify_error(exc)
        raise HTTPException(http_code, msg)


@router.get("/quality")
async def data_quality(auth: AuthContext = Depends(require_auth)):
    try:
        with shared_db_session() as db:
            rows = db.execute(text("SELECT * FROM v_tenant_health")).fetchall()
        return {"tenants": [dict(r._mapping) for r in rows],
                "checked_at": datetime.utcnow().isoformat()}
    except Exception as exc:
        http_code, msg = _classify_error(exc)
        raise HTTPException(http_code, msg)


@router.get("/partitions")
async def partition_health(auth: AuthContext = Depends(require_admin)):
    try:
        with shared_db_session() as db:
            rows = db.execute(text("SELECT * FROM v_partition_stats")).fetchall()
        return {"partitions": [dict(r._mapping) for r in rows],
                "checked_at": datetime.utcnow().isoformat()}
    except Exception as exc:
        http_code, msg = _classify_error(exc)
        raise HTTPException(http_code, msg)


@router.get("/scheduler")
async def get_scheduler_status(auth: AuthContext = Depends(require_admin)):
    """
    CDC pipeline status (replaces the old in-process SyncScheduler).
    Returns a summary of cdc_inbox / cdc_dead_letter / cdc_watermarks,
    or {available: false} when the new schema has not yet been applied
    (the API server no longer manages the scheduler).
    """
    try:
        with shared_db_session() as db:
            inbox = db.execute(text("""
                SELECT status, count(*) FROM cdc_inbox GROUP BY status
            """)).fetchall()
            dlq = db.execute(text("SELECT count(*) FROM cdc_dead_letter")).scalar() or 0
            wm = db.execute(text("""
                SELECT source_id, table_name, last_change_id, last_acked_at
                  FROM cdc_watermarks ORDER BY source_id, table_name
            """)).fetchall()
        return {
            "available": True,
            "managed_by": "out-of-process services/cdc_worker + services/etl_worker",
            "inbox": {row[0]: int(row[1]) for row in inbox},
            "dead_letter_total": int(dlq),
            "watermarks": [
                {"source_id": r[0], "table_name": r[1],
                 "last_change_id": int(r[2]),
                 "last_acked_at": r[3].isoformat() if r[3] else None}
                for r in wm
            ],
        }
    except Exception as exc:
        return {"available": False, "reason": str(exc)}


# ── Multi-DB support ──────────────────────────────────────────────────────────

_sync_config_cache: Optional[Dict[str, Any]] = None
_MAX_PARALLEL_SOURCES = 3
_SOURCE_TIMEOUT_S     = 30.0


def _load_sync_config() -> Dict[str, Any]:
    """Load and cache sync_config.json. Handles UTF-8 BOM written by Windows."""
    global _sync_config_cache
    if _sync_config_cache is not None:
        return _sync_config_cache
    config_path = os.path.join(backend_dir, "..", "config", "sync_config.json")
    try:
        with open(config_path, encoding="utf-8-sig") as f:
            _sync_config_cache = json.load(f)
    except Exception as exc:
        raise RuntimeError(f"sync_config.json missing or unreadable: {exc}") from exc
    return _sync_config_cache


class MultiSyncRequest(BaseModel):
    # tenant_id is intentionally absent — always read from sync_config.json per source
    limit: Optional[int] = None


def _run_single_source_sync(
    source_id: str, conn_str: str, tenant_id: int, limit: Optional[int]
) -> Dict[str, Any]:
    """
    Sync one source through MultiDBPipeline.
    Always returns a result dict — never raises — so the caller can aggregate
    partial failures without try/except wrappers.
    """
    t0 = time.monotonic()
    try:
        from cdc.adapter_factory import CDCAdapterFactory
        from etl.multi_db_pipeline import MultiDBPipeline
    except Exception as exc:
        return {
            "source": source_id, "status": "failed",
            "records_processed": 0,
            "duration_ms": round((time.monotonic() - t0) * 1000, 1),
            "error": f"import error: {exc}",
        }
    try:
        adapter = CDCAdapterFactory.create_adapter(conn_str)
        if not adapter.validate_connection():
            return {
                "source": source_id, "status": "failed",
                "records_processed": 0,
                "duration_ms": round((time.monotonic() - t0) * 1000, 1),
                "error": f"Cannot connect to {source_id}",
            }
        pipe  = MultiDBPipeline(adapter, tenant_id=tenant_id)
        stats = pipe.sync_all(limit=limit)
        adapter.close()
        return {
            "source": source_id,
            "status": "ok",
            "records_processed": sum(v["loaded"] for v in stats.values()),
            "duration_ms": round((time.monotonic() - t0) * 1000, 1),
            "error": None,
        }
    except Exception as exc:
        logger.error("[multi-sync] %s: %s", source_id, exc, exc_info=True)
        return {
            "source": source_id, "status": "failed",
            "records_processed": 0,
            "duration_ms": round((time.monotonic() - t0) * 1000, 1),
            "error": str(exc),
        }


def _run_multi_db_sync(
    sync_id: str,
    triggered_by: str,
    sources: List[Dict[str, Any]],
    limit: Optional[int],
    sync_type: str,
) -> None:
    """
    Background body: run sources in parallel (≤ _MAX_PARALLEL_SOURCES at once)
    with a per-execution-round timeout.  One failure never aborts the others.

    Tenant IDs are read exclusively from the source config dicts — they are
    never accepted from the HTTP request body (security fix).
    """
    sync_store.start_run(sync_id, current_step="initialising")
    results: Dict[str, Any] = {}
    n          = max(1, len(sources))
    wall_start = time.monotonic()

    # Budget = one 30 s window per execution round of _MAX_PARALLEL_SOURCES.
    # e.g. 5 sources / 3 parallel → 2 rounds → 60 s total ceiling.
    total_budget = math.ceil(n / _MAX_PARALLEL_SOURCES) * _SOURCE_TIMEOUT_S

    future_to_sid: Dict[Any, str] = {}
    with ThreadPoolExecutor(max_workers=min(_MAX_PARALLEL_SOURCES, n)) as pool:
        for src in sources:
            sid = src["id"]
            cs  = src.get("connection_string", "")
            tid = src.get("tenant_id", 1)   # tenant always from config, not client
            f   = pool.submit(_run_single_source_sync, sid, cs, tid, limit)
            future_to_sid[f] = sid

        sync_store.update_progress(sync_id, progress=10,
                                   current_step=f"running {n} source(s) in parallel")

        done, not_done = cf_wait(list(future_to_sid.keys()), timeout=total_budget)

    # Collect results from futures that finished within the budget
    for f in done:
        sid = future_to_sid[f]
        try:
            results[sid] = f.result()
        except Exception as exc:
            results[sid] = {
                "source": sid, "status": "failed",
                "records_processed": 0,
                "duration_ms": 0,
                "error": str(exc),
            }

    # Mark futures that exceeded the budget as timed-out
    for f in not_done:
        f.cancel()   # prevents start for still-queued futures; no-op if running
        sid = future_to_sid[f]
        results[sid] = {
            "source": sid, "status": "failed",
            "records_processed": 0,
            "duration_ms": round(total_budget * 1000),
            "error": f"Timed out after {int(total_budget)}s",
        }
        logger.warning("[multi-sync %s] %s timed out after %.0fs", sync_id, sid, total_budget)

    # Aggregate
    successful        = sum(1 for r in results.values() if r["status"] == "ok")
    failed_count      = len(sources) - successful
    total_records     = sum(r.get("records_processed", 0) for r in results.values())
    total_duration_ms = round((time.monotonic() - wall_start) * 1000, 1)

    if failed_count == 0:
        overall = "success"
    elif successful == 0:
        overall = "failed"
    else:
        overall = "partial_success"

    records: Dict[str, Any] = {
        "overall":           overall,
        "total_sources":     len(sources),
        "successful":        successful,
        "failed":            failed_count,
        "total_records":     total_records,
        "total_duration_ms": total_duration_ms,
        "results":           results,
    }

    sync_store.update_progress(sync_id, progress=95, current_step="finalising",
                               records_processed=records)
    if overall == "failed":
        sync_store.fail_run(sync_id, "All sources failed to sync")
    else:
        sync_store.complete_run(sync_id, records_processed=records)

    event_log.write(
        'SYNC_COMPLETED' if overall != 'failed' else 'SYNC_FAILED',
        triggered_by, 0,
        f"Multi-DB {sync_type} sync {sync_id}: {overall}",
        records,
    )
    logger.info(
        "[multi-sync %s] done overall=%s records=%d failed=%d ms=%.0f",
        sync_id, overall, total_records, failed_count, total_duration_ms,
    )


# Multi-DB endpoints use tenant_id=0 as the advisory-lock sentinel so that
# only one multi-DB run can be active at a time (per-tenant runs are unaffected).

@router.post("/multi/full", status_code=202)
async def trigger_multi_full_sync(
    request: MultiSyncRequest,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(require_admin),
):
    """
    Full ETL sync across ALL configured database sources (sync_config.json).
    Each source runs extract→transform→load independently; one failure does
    not abort the others.  Returns 202 with sync_id for polling.
    """
    try:
        config = _load_sync_config()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    sources = config.get("sources", [])
    if not sources:
        raise HTTPException(422, "No sources configured in sync_config.json")

    sync_id, conflicting, reaped = sync_store.trigger_atomic(
        0, sync_type="multi_full", triggered_by=auth.email,
    )
    if reaped:
        event_log.write('SYNC_REAPED', auth.email, 0,
                        f"Reaped {reaped} stale multi-sync run(s)", {"reaped": reaped})
    if conflicting is not None:
        raise HTTPException(
            409,
            f"Multi-DB sync {conflicting['sync_id']} is already {conflicting['status']}. "
            "Wait for it to finish or poll /api/v1/sync/status.",
        )

    event_log.write('SYNC_TRIGGERED', auth.email, 0,
                    f"Multi-DB full sync {sync_id} triggered ({len(sources)} sources)", {})

    background_tasks.add_task(
        _run_multi_db_sync, sync_id, auth.email, sources, request.limit, "full"
    )
    return {
        "status":       "queued",
        "message":      f"Multi-DB full sync queued for {len(sources)} source(s).",
        "sync_id":      sync_id,
        "mode":         "multi_full",
        "sources":      [s["id"] for s in sources],
        "triggered_by": auth.email,
    }


@router.post("/multi/incremental", status_code=202)
async def trigger_multi_incremental_sync(
    request: MultiSyncRequest,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(require_admin),
):
    """
    Incremental sync across ALL configured database sources.
    Applies a 1000-row cap per resource per source unless the caller supplies
    a custom limit.  Sources without native CDC use a bounded full extraction.
    Returns 202 with sync_id for polling.
    """
    try:
        config = _load_sync_config()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    sources = config.get("sources", [])
    if not sources:
        raise HTTPException(422, "No sources configured in sync_config.json")

    effective_limit = request.limit if request.limit is not None else 1000

    sync_id, conflicting, reaped = sync_store.trigger_atomic(
        0, sync_type="multi_incremental", triggered_by=auth.email,
    )
    if reaped:
        event_log.write('SYNC_REAPED', auth.email, 0,
                        f"Reaped {reaped} stale multi-sync run(s)", {"reaped": reaped})
    if conflicting is not None:
        raise HTTPException(
            409,
            f"Multi-DB sync {conflicting['sync_id']} is already {conflicting['status']}.",
        )

    event_log.write('SYNC_TRIGGERED', auth.email, 0,
                    f"Multi-DB incremental sync {sync_id} triggered ({len(sources)} sources)", {})

    background_tasks.add_task(
        _run_multi_db_sync, sync_id, auth.email, sources, effective_limit, "incremental"
    )
    return {
        "status":       "queued",
        "message":      f"Multi-DB incremental sync queued for {len(sources)} source(s).",
        "sync_id":      sync_id,
        "mode":         "multi_incremental",
        "sources":      [s["id"] for s in sources],
        "limit":        effective_limit,
        "triggered_by": auth.email,
    }


@router.post("/multi/{source_id}", status_code=202)
async def trigger_single_source_sync(
    source_id: str,
    request: MultiSyncRequest,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(require_admin),
):
    """
    Full ETL sync for a SINGLE named source (e.g. "postgres_hospital").
    Source ID must match an entry in sync_config.json.  Returns 404 if unknown.
    tenant_id is always read from config — never accepted from the client.
    """
    try:
        config = _load_sync_config()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    sources = config.get("sources", [])
    src = next((s for s in sources if s["id"] == source_id), None)
    if src is None:
        known = [s["id"] for s in sources]
        raise HTTPException(
            404,
            f"Source '{source_id}' not found. Known sources: {known}",
        )

    tenant_id = src.get("tenant_id", 1)   # from config only — not from request

    sync_id, conflicting, reaped = sync_store.trigger_atomic(
        0, sync_type=f"multi_{source_id}", triggered_by=auth.email,
    )
    if reaped:
        event_log.write('SYNC_REAPED', auth.email, 0,
                        f"Reaped {reaped} stale multi-sync run(s)", {"reaped": reaped})
    if conflicting is not None:
        raise HTTPException(
            409,
            f"Multi-DB sync {conflicting['sync_id']} is already {conflicting['status']}.",
        )

    event_log.write('SYNC_TRIGGERED', auth.email, 0,
                    f"Single-source sync {sync_id} for '{source_id}' triggered", {})

    background_tasks.add_task(
        _run_multi_db_sync, sync_id, auth.email, [src], request.limit, f"single:{source_id}",
    )
    return {
        "status":       "queued",
        "message":      f"Sync queued for source '{source_id}'.",
        "sync_id":      sync_id,
        "mode":         f"multi_{source_id}",
        "source_id":    source_id,
        "tenant_id":    tenant_id,
        "triggered_by": auth.email,
    }
