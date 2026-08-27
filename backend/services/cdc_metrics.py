"""
CDC-derived runtime metrics.

Sole input is the live state of the shared-DB CDC tables:
  cdc_inbox, cdc_dead_letter, cdc_watermarks.

All queries are bounded (windowed by time or capped by LIMIT) so a single
HTTP probe cannot trigger a full scan of an unbounded queue.

Returned shape:
  {
    "ingestion_lag_seconds":   float | None,  # source_ts of latest event vs now
    "processing_lag_seconds":  float | None,  # oldest pending row vs now
    "throughput_per_min":      int,           # rows moved to done in last 60s
    "error_rate":              float,         # DLQ / (DLQ + done) over last hour
    "queue_depth":             int,           # pending + in_progress + parked
    "dead_letter_count":       int,           # all-time DLQ rows
    "active_sources":          int,           # sources acked within last 5 min
    "available":               bool,          # False when CDC schema not applied
  }
"""
from __future__ import annotations

from typing import Any, Dict
import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# Time windows (seconds)
THROUGHPUT_WINDOW = 60
ERROR_RATE_WINDOW = 3600
ACTIVE_SOURCE_WINDOW = 300

# Hard cap on rows scanned per windowed count, in case the index isn't used.
SCAN_CAP = 50_000

EMPTY: Dict[str, Any] = {
    "ingestion_lag_seconds": None,
    "processing_lag_seconds": None,
    "throughput_per_min": 0,
    "error_rate": 0.0,
    "queue_depth": 0,
    "dead_letter_count": 0,
    "active_sources": 0,
    "available": False,
}


def _capped_count(db, sql_inner: str, params: dict | None = None) -> int:
    """COUNT with a LIMIT guard so an unindexed scan can't blow up."""
    sql = f"SELECT count(*) FROM ( {sql_inner} LIMIT {SCAN_CAP} ) t"
    return int(db.execute(text(sql), params or {}).scalar() or 0)


def _schema_present(db) -> bool:
    row = db.execute(text("""
        SELECT to_regclass('public.cdc_inbox') IS NOT NULL
           AND to_regclass('public.cdc_dead_letter') IS NOT NULL
           AND to_regclass('public.cdc_watermarks') IS NOT NULL
    """)).scalar()
    return bool(row)


def get_cdc_metrics(db) -> Dict[str, Any]:
    """Return real-time CDC pipeline metrics. Never raises — returns EMPTY on fault."""
    try:
        if not _schema_present(db):
            return dict(EMPTY)

        # ── ingestion_lag: how stale is the latest event we received? ──────
        # PK index gives us the most-recent row in O(1).
        ingestion_lag = db.execute(text("""
            SELECT EXTRACT(EPOCH FROM (now() - source_ts))
              FROM cdc_inbox
             ORDER BY id DESC
             LIMIT 1
        """)).scalar()

        # ── processing_lag: oldest pending row's age ────────────────────────
        # Uses partial index cdc_inbox_partition_order_idx WHERE status='pending'.
        processing_lag = db.execute(text("""
            SELECT EXTRACT(EPOCH FROM (now() - min(received_at)))
              FROM cdc_inbox
             WHERE status = 'pending'
        """)).scalar()

        # ── throughput: rows moved to 'done' in last 60s ────────────────────
        # Uses cdc_inbox_processed_at_idx WHERE status='done'.
        throughput = _capped_count(db, """
            SELECT 1 FROM cdc_inbox
             WHERE status = 'done'
               AND processed_at > now() - make_interval(secs => :win)
        """, {"win": THROUGHPUT_WINDOW})

        # ── error_rate: DLQ vs done over a rolling hour ─────────────────────
        dlq_recent = _capped_count(db, """
            SELECT 1 FROM cdc_dead_letter
             WHERE failed_at > now() - make_interval(secs => :win)
        """, {"win": ERROR_RATE_WINDOW})
        done_recent = _capped_count(db, """
            SELECT 1 FROM cdc_inbox
             WHERE status = 'done'
               AND processed_at > now() - make_interval(secs => :win)
        """, {"win": ERROR_RATE_WINDOW})
        denom = dlq_recent + done_recent
        error_rate = (dlq_recent / denom) if denom > 0 else 0.0

        # ── queue_depth: rows still in flight ───────────────────────────────
        # Three partial indexes cover pending / in_progress (none) / parked.
        queue_depth = int(db.execute(text("""
            SELECT count(*) FROM cdc_inbox
             WHERE status IN ('pending','in_progress','parked')
        """)).scalar() or 0)

        dead_letter_total = int(db.execute(text(
            "SELECT count(*) FROM cdc_dead_letter"
        )).scalar() or 0)

        # ── active_sources: sources acked recently ──────────────────────────
        active_sources = int(db.execute(text("""
            SELECT count(DISTINCT source_id) FROM cdc_watermarks
             WHERE last_acked_at > now() - make_interval(secs => :win)
        """), {"win": ACTIVE_SOURCE_WINDOW}).scalar() or 0)

        return {
            "ingestion_lag_seconds":  float(ingestion_lag) if ingestion_lag is not None else None,
            "processing_lag_seconds": float(processing_lag) if processing_lag is not None else None,
            "throughput_per_min":     throughput,
            "error_rate":             round(error_rate, 6),
            "queue_depth":            queue_depth,
            "dead_letter_count":      dead_letter_total,
            "active_sources":         active_sources,
            "available":              True,
        }
    except SQLAlchemyError as exc:
        logger.warning(f"CDC metrics query failed: {exc}")
        return dict(EMPTY)
