"""
Sync run persistence — PostgreSQL-backed (shared DB, table `sync_runs`).

Replaces the in-memory `sync_state` dict so sync state survives restarts,
supports multi-worker deployments, and can be queried via SQL.

Lifecycle:
    create_run()  -> status='queued'   -> returns sync_id
    start_run()   -> status='running'
    update_progress() -> bumps progress/records AND `updated_at` (heartbeat)
    complete_run() -> status='completed' with stats
    fail_run()     -> status='failed' with error

Heartbeat / stale detection:
    `updated_at` doubles as a heartbeat. Any state change bumps it. A run
    whose updated_at is older than STALE_AFTER_MINUTES while still in
    queued/running is considered a zombie and gets reaped (status='failed',
    error='timeout / zombie sync') by reap_stale_for_tenant() — called
    before each new trigger and by the explicit /sync/reset admin route.

Concurrency: callers serialize per-tenant via pg_advisory_xact_lock(tenant_id)
inside a transaction that does (reap-stale → check-active → insert) atomically.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from common.database import shared_db_session

logger = logging.getLogger(__name__)

# A queued/running sync whose updated_at is older than this is zombie.
STALE_AFTER_MINUTES = 10


def _row_to_dict(row) -> Dict[str, Any]:
    d = dict(row._mapping)
    for k in ("started_at", "completed_at", "updated_at"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat() if hasattr(d[k], "isoformat") else d[k]
    if "sync_id" in d and d["sync_id"] is not None:
        d["sync_id"] = str(d["sync_id"])
    # records_processed comes back as dict already (jsonb)
    return d


def is_stale_run(run: Optional[Dict[str, Any]],
                 threshold_minutes: int = STALE_AFTER_MINUTES) -> bool:
    """Return True if `run` is queued/running but its heartbeat is older than threshold."""
    if not run or run.get("status") not in ("queued", "running"):
        return False
    hb = run.get("updated_at")
    if not hb:
        return False
    try:
        hb_dt = datetime.fromisoformat(hb) if isinstance(hb, str) else hb
        # sync_runs.updated_at is naive UTC; treat as UTC for comparison
        if hb_dt.tzinfo is None:
            hb_dt = hb_dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - hb_dt) > timedelta(minutes=threshold_minutes)
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Writers
# ─────────────────────────────────────────────────────────────────────────────
def create_run(
    tenant_id: int,
    sync_type: str,
    triggered_by: Optional[str] = None,
) -> str:
    """Insert a new run in status='queued'. Returns sync_id (str UUID)."""
    sync_id = str(uuid.uuid4())
    with shared_db_session() as db:
        db.execute(
            text("""
                INSERT INTO sync_runs
                    (sync_id, tenant_id, sync_type, status, triggered_by)
                VALUES
                    (:sid, :tid, :typ, 'queued', :by)
            """),
            {"sid": sync_id, "tid": tenant_id, "typ": sync_type, "by": triggered_by},
        )
    return sync_id


def start_run(sync_id: str, current_step: str = "starting") -> None:
    with shared_db_session() as db:
        db.execute(
            text("""
                UPDATE sync_runs
                   SET status='running',
                       current_step=:step,
                       updated_at=CURRENT_TIMESTAMP
                 WHERE sync_id=:sid
            """),
            {"sid": sync_id, "step": current_step},
        )


def update_progress(
    sync_id: str,
    progress: Optional[int] = None,
    current_step: Optional[str] = None,
    records_processed: Optional[Dict[str, Any]] = None,
    last_checkpoint: Optional[int] = None,
) -> None:
    """Patch live progress fields. All args optional — only set what's provided."""
    sets, params = [], {"sid": sync_id}
    if progress is not None:
        sets.append("progress=:prog")
        params["prog"] = max(0, min(100, int(progress)))
    if current_step is not None:
        sets.append("current_step=:step")
        params["step"] = current_step
    if records_processed is not None:
        sets.append("records_processed=CAST(:rec AS jsonb)")
        params["rec"] = json.dumps(records_processed)  # noqa: F841
    if last_checkpoint is not None:
        sets.append("last_checkpoint=:ckpt")
        params["ckpt"] = last_checkpoint
    if not sets:
        return
    sets.append("updated_at=CURRENT_TIMESTAMP")
    with shared_db_session() as db:
        db.execute(
            text(f"UPDATE sync_runs SET {', '.join(sets)} WHERE sync_id=:sid"),
            params,
        )


def complete_run(sync_id: str, records_processed: Dict[str, Any]) -> None:
    with shared_db_session() as db:
        db.execute(
            text("""
                UPDATE sync_runs
                   SET status='completed',
                       progress=100,
                       current_step='done',
                       records_processed=CAST(:rec AS jsonb),
                       completed_at=CURRENT_TIMESTAMP,
                       updated_at=CURRENT_TIMESTAMP
                 WHERE sync_id=:sid
            """),
            {"sid": sync_id, "rec": json.dumps(records_processed)},
        )


def fail_run(sync_id: str, error: str) -> None:
    with shared_db_session() as db:
        db.execute(
            text("""
                UPDATE sync_runs
                   SET status='failed',
                       error_message=:err,
                       completed_at=CURRENT_TIMESTAMP,
                       updated_at=CURRENT_TIMESTAMP
                 WHERE sync_id=:sid
            """),
            {"sid": sync_id, "err": error[:4000]},
        )


def heartbeat(sync_id: str) -> None:
    """Bump updated_at for a running sync without changing other fields.
    Use when a long-running step has no progress increment to report."""
    with shared_db_session() as db:
        db.execute(
            text("UPDATE sync_runs SET updated_at=CURRENT_TIMESTAMP WHERE sync_id=:sid"),
            {"sid": sync_id},
        )


def reap_stuck_runs(older_than_minutes: int = 60,
                    error_message: str = "Reaped: process exited while running") -> int:
    """Mark runs stuck in 'queued/running' older than N minutes as failed.
    Called on scheduler startup to clean up orphans from crashed workers.
    Returns number of rows reaped."""
    with shared_db_session() as db:
        result = db.execute(
            text("""
                UPDATE sync_runs
                   SET status='failed',
                       error_message=:err,
                       completed_at=CURRENT_TIMESTAMP,
                       updated_at=CURRENT_TIMESTAMP
                 WHERE status IN ('queued','running')
                   AND updated_at < CURRENT_TIMESTAMP - (CAST(:mins AS text) || ' minutes')::interval
            """),
            {"mins": older_than_minutes, "err": error_message},
        )
        return result.rowcount or 0


def reap_stale_for_tenant(tenant_id: int,
                          threshold_minutes: int = STALE_AFTER_MINUTES,
                          db=None) -> int:
    """Reap zombie runs for a single tenant. Used inline by trigger endpoints.

    May be called inside an existing transaction (`db` passed in) or open its
    own session (`db=None`).
    """
    sql = text("""
        UPDATE sync_runs
           SET status='failed',
               error_message='timeout / zombie sync',
               completed_at=CURRENT_TIMESTAMP,
               updated_at=CURRENT_TIMESTAMP
         WHERE tenant_id=:tid
           AND status IN ('queued','running')
           AND updated_at < CURRENT_TIMESTAMP - (CAST(:mins AS text) || ' minutes')::interval
    """)
    params = {"tid": tenant_id, "mins": threshold_minutes}
    if db is not None:
        return db.execute(sql, params).rowcount or 0
    with shared_db_session() as session:
        return session.execute(sql, params).rowcount or 0


def trigger_atomic(tenant_id: int, sync_type: str,
                   triggered_by: Optional[str],
                   stale_threshold_minutes: int = STALE_AFTER_MINUTES
                   ) -> tuple[Optional[str], Optional[Dict[str, Any]], int]:
    """Atomic per-tenant trigger.

    Within a single transaction, holds a pg_advisory_xact_lock on tenant_id,
    reaps stale runs, checks for an active run, and inserts a new queued row
    if none. Returns a tuple (sync_id_or_None, conflicting_active_run_or_None,
    reaped_count).

    Caller should:
      - if sync_id is not None → schedule background task with this id
      - if conflicting_active_run is not None → return 409 to client
    """
    with shared_db_session() as db:
        # Per-tenant serialization: any other transaction trying to trigger
        # for the same tenant blocks until this one commits or rolls back.
        db.execute(text("SELECT pg_advisory_xact_lock(:tid)"), {"tid": tenant_id})

        reaped = reap_stale_for_tenant(tenant_id, stale_threshold_minutes, db=db)

        active_row = db.execute(
            text("""
                SELECT sync_id, status, started_at, updated_at
                  FROM sync_runs
                 WHERE tenant_id=:tid AND status IN ('queued','running')
                 ORDER BY started_at DESC LIMIT 1
            """),
            {"tid": tenant_id},
        ).fetchone()
        if active_row is not None:
            return None, _row_to_dict(active_row), reaped

        sync_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO sync_runs (sync_id, tenant_id, sync_type, status, triggered_by)
                VALUES (:sid, :tid, :typ, 'queued', :by)
            """),
            {"sid": sync_id, "tid": tenant_id, "typ": sync_type, "by": triggered_by},
        )
        return sync_id, None, reaped


def tenant_sync_rate(tenant_id: int) -> Optional[float]:
    """Compute success rate from sync_runs history.

    Formula: completed / (completed + failed). Returns:
      - None when there are 0 terminal runs (insufficient data)
      - float in [0.0, 1.0] otherwise
    """
    with shared_db_session() as db:
        row = db.execute(
            text("""
                SELECT
                  SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS ok,
                  SUM(CASE WHEN status='failed'    THEN 1 ELSE 0 END) AS bad
                FROM sync_runs
                WHERE tenant_id=:tid AND status IN ('completed','failed')
            """),
            {"tid": tenant_id},
        ).fetchone()
    if not row:
        return None
    ok = int(row[0] or 0)
    bad = int(row[1] or 0)
    total = ok + bad
    if total == 0:
        return None
    rate = ok / total
    return max(0.0, min(1.0, rate))


# ─────────────────────────────────────────────────────────────────────────────
# Readers
# ─────────────────────────────────────────────────────────────────────────────
def get_run(sync_id: str) -> Optional[Dict[str, Any]]:
    with shared_db_session() as db:
        row = db.execute(
            text("SELECT * FROM sync_runs WHERE sync_id=:sid"),
            {"sid": sync_id},
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_active_run(tenant_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Return the current queued-or-running run (per tenant, or global)."""
    sql = """
        SELECT * FROM sync_runs
         WHERE status IN ('queued','running')
    """
    params: Dict[str, Any] = {}
    if tenant_id is not None:
        sql += " AND tenant_id=:tid"
        params["tid"] = tenant_id
    sql += " ORDER BY started_at DESC LIMIT 1"
    with shared_db_session() as db:
        row = db.execute(text(sql), params).fetchone()
    return _row_to_dict(row) if row else None


def get_latest_run(tenant_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    sql = "SELECT * FROM sync_runs"
    params: Dict[str, Any] = {}
    if tenant_id is not None:
        sql += " WHERE tenant_id=:tid"
        params["tid"] = tenant_id
    sql += " ORDER BY started_at DESC LIMIT 1"
    with shared_db_session() as db:
        row = db.execute(text(sql), params).fetchone()
    return _row_to_dict(row) if row else None


def list_runs(
    tenant_id: Optional[int] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM sync_runs"
    params: Dict[str, Any] = {"lim": limit}
    if tenant_id is not None:
        sql += " WHERE tenant_id=:tid"
        params["tid"] = tenant_id
    sql += " ORDER BY started_at DESC LIMIT :lim"
    with shared_db_session() as db:
        rows = db.execute(text(sql), params).fetchall()
    return [_row_to_dict(r) for r in rows]


def total_syncs(tenant_id: Optional[int] = None) -> int:
    sql = "SELECT COUNT(*) FROM sync_runs WHERE status='completed'"
    params: Dict[str, Any] = {}
    if tenant_id is not None:
        sql += " AND tenant_id=:tid"
        params["tid"] = tenant_id
    with shared_db_session() as db:
        return db.execute(text(sql), params).scalar() or 0
