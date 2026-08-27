"""
ETL Worker core.

Claims one (source_id, table_name) partition at a time using FOR UPDATE
SKIP LOCKED, then processes its rows in source_seq order. Rows are
delegated to backend.etl.incremental_sync.IncrementalSync handlers so
the actual write logic is reused, not reimplemented.

Reclaim: rows stuck in 'in_progress' past ETL_CLAIM_TIMEOUT_SECONDS are
returned to 'pending' on idle ticks (covers crashed workers).
"""
from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text

from services.common.backoff import exp_backoff_ms
from services.common.config import shared_db_url

# Reuse existing per-record handlers
import sys
_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _BACKEND)
sys.path.insert(0, os.path.join(_BACKEND, "etl"))
from incremental_sync import IncrementalSync  # noqa: E402

logger = logging.getLogger("cdc.etl.core")


@dataclass
class ETLStatus:
    worker_id: str
    started_at: float = field(default_factory=time.time)
    current_partition: Optional[Tuple[str, str]] = None
    last_processed_at: Optional[float] = None
    last_error: Optional[str] = None
    rows_done: int = 0
    rows_retried: int = 0
    rows_dlq: int = 0
    rows_parked: int = 0


class ETLWorker:
    BATCH_SIZE = int(os.environ.get("ETL_BATCH_SIZE", "200"))
    MAX_ATTEMPTS = int(os.environ.get("ETL_MAX_ATTEMPTS", "8"))
    INITIAL_BACKOFF_MS = int(os.environ.get("ETL_INITIAL_BACKOFF_MS", "1000"))
    MAX_BACKOFF_MS = int(os.environ.get("ETL_MAX_BACKOFF_MS", "60000"))
    CLAIM_TIMEOUT_SECONDS = int(os.environ.get("ETL_CLAIM_TIMEOUT_SECONDS", "120"))
    FK_MAX_WAIT_SECONDS = int(os.environ.get("ETL_FK_MAX_WAIT_SECONDS", "300"))
    IDLE_SLEEP_SECONDS = float(os.environ.get("ETL_IDLE_SLEEP_SECONDS", "2"))

    def __init__(self) -> None:
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self.engine = create_engine(shared_db_url(), pool_pre_ping=True, future=True)
        self._stop = threading.Event()
        self.status = ETLStatus(worker_id=self.worker_id)
        # Lazily build IncrementalSync per tenant — most events route via
        # the shared handlers; tenant_id taken from payload when present.
        self._sync_cache: Dict[int, IncrementalSync] = {}

    def request_stop(self) -> None:
        self._stop.set()

    # ── main loops ───────────────────────────────────────────────────────────
    def run_forever(self) -> None:
        last_reclaim = 0.0
        while not self._stop.is_set():
            now = time.time()
            if now - last_reclaim >= 30:
                self._reclaim_stuck()
                last_reclaim = now

            processed = self.process_one_partition()
            if processed == 0:
                if self._stop.wait(timeout=self.IDLE_SLEEP_SECONDS):
                    break
        logger.info("etl_worker_exit worker=%s", self.worker_id)

    def process_one_partition(self) -> int:
        """Claim and process one batch from one partition. Returns rows handled."""
        rows = self._claim_batch()
        if not rows:
            self.status.current_partition = None
            return 0

        partition = (rows[0]["source_id"], rows[0]["table_name"])
        self.status.current_partition = partition

        registry = self._load_registry_entry(*partition)
        for row in rows:
            self._process_row(row, registry)
        self.status.last_processed_at = time.time()
        return len(rows)

    # ── claim ────────────────────────────────────────────────────────────────
    def _claim_batch(self) -> List[Dict]:
        with self.engine.begin() as conn:
            # Step 1: pick the ready partition with the oldest pending row.
            # GROUP BY + FOR UPDATE is not allowed in PostgreSQL, so we use a
            # plain SELECT (no lock) to choose (source_id, table_name), then
            # immediately lock individual rows in step 2.
            part = conn.execute(text("""
                SELECT source_id, table_name
                  FROM cdc_inbox
                 WHERE status = 'pending'
                   AND next_attempt_at <= now()
                 GROUP BY source_id, table_name
                 ORDER BY MIN(source_seq)
                 LIMIT 1
            """)).fetchone()
            if part is None:
                return []

            # Step 2: claim a batch of rows from that partition.
            result = conn.execute(text("""
                UPDATE cdc_inbox c
                   SET status     = 'in_progress',
                       claimed_at = now(),
                       claimed_by = :wid,
                       attempts   = attempts + 1
                  FROM (
                    SELECT id
                      FROM cdc_inbox
                     WHERE source_id   = :src
                       AND table_name  = :tbl
                       AND status      = 'pending'
                       AND next_attempt_at <= now()
                     ORDER BY source_seq
                     LIMIT :batch_size
                     FOR UPDATE SKIP LOCKED
                  ) sel
                 WHERE c.id = sel.id
                RETURNING c.id, c.source_id, c.table_name, c.source_seq,
                          c.change_id, c.op, c.pk, c.payload, c.payload_before,
                          c.schema_version, c.attempts
            """), {
                "wid": self.worker_id,
                "src": part.source_id,
                "tbl": part.table_name,
                "batch_size": self.BATCH_SIZE,
            }).fetchall()
        return [dict(r._mapping) for r in result]

    def _reclaim_stuck(self) -> None:
        try:
            with self.engine.begin() as conn:
                conn.execute(text(f"""
                    UPDATE cdc_inbox
                       SET status='pending', next_attempt_at = now()
                     WHERE status='in_progress'
                       AND claimed_at < now() - INTERVAL '{int(self.CLAIM_TIMEOUT_SECONDS)} seconds'
                """))
        except Exception as exc:
            logger.warning("reclaim_failed: %s", exc)

    # ── per-row processing ───────────────────────────────────────────────────
    def _process_row(self, row: Dict, registry: Optional[Dict]) -> None:
        try:
            outcome, error_class, detail = self._apply_row(row, registry)
        except Exception as exc:
            outcome, error_class, detail = "retry", "permanent_etl", repr(exc)

        if outcome == "done":
            self._mark_done(row["id"])
            self.status.rows_done += 1
            return

        if outcome == "park":
            self._park_row(row["id"], error_class, detail)
            self.status.rows_parked += 1
            return

        if outcome == "dlq":
            self._dlq_row(row, error_class, detail)
            self.status.rows_dlq += 1
            return

        # retry path
        attempts = int(row["attempts"])
        if attempts >= self.MAX_ATTEMPTS:
            self._dlq_row(row, "exhausted", detail)
            self.status.rows_dlq += 1
            return
        # FK-late: also bound by wall clock
        if error_class == "fk_pending":
            received_at = row.get("received_at")
            # Use a quick time check via DB to avoid clock-skew
            if self._exceeds_fk_wait(row["id"]):
                self._dlq_row(row, "fk_unresolved", detail)
                self.status.rows_dlq += 1
                return
        delay_ms = exp_backoff_ms(
            attempts,
            initial_ms=self.INITIAL_BACKOFF_MS,
            max_ms=self.MAX_BACKOFF_MS,
            jitter_pct=20,
        )
        self._mark_retry(row["id"], error_class, detail, delay_ms)
        self.status.rows_retried += 1
        self.status.last_error = f"{error_class}: {detail[:300]}"

    def _apply_row(self, row: Dict, registry: Optional[Dict]) -> Tuple[str, str, str]:
        """
        Returns (outcome, error_class, detail).
        outcome: 'done' | 'retry' | 'park' | 'dlq'
        """
        if registry is None:
            return ("park", "schema_drift_park",
                    f"no registry entry for ({row['source_id']},{row['table_name']})")
        if registry.get("status") != "active":
            return ("park", "schema_drift_park",
                    f"registry status={registry.get('status')!r}")

        table = row["table_name"]
        op = row["op"]
        payload = row.get("payload") or {}
        pk = row.get("pk") or {}

        # Reuse IncrementalSync handlers — they already write FHIR with RLS context.
        tenant_id = self._infer_tenant_id(payload)
        sync = self._get_sync(tenant_id)
        record_id = pk.get("record_id")
        if record_id is None:
            return ("dlq", "validation", f"missing pk.record_id in event {row['change_id']}")

        op_word = {"I": "INSERT", "U": "UPDATE", "D": "DELETE"}.get(op, "UPDATE")

        handler = {
            "patients":    sync._sync_patient,
            "encounters":  sync._sync_encounter,
            "lab_results": sync._sync_observation,
            "medications": sync._sync_medication,
        }.get(table)

        if handler is None:
            return ("park", "schema_drift_park", f"no handler for table {table!r}")

        try:
            ok = handler(record_id, op_word)
        except Exception as exc:
            msg = str(exc)
            low = msg.lower()
            if "foreign key" in low or "violates foreign key" in low:
                return ("retry", "fk_pending", msg)
            if "not null" in low or "check constraint" in low:
                return ("dlq", "permanent_etl", msg)
            return ("retry", "permanent_etl", msg)

        if ok:
            return ("done", "", "")
        return ("retry", "etl_handler_failed", "handler returned False")

    @staticmethod
    def _infer_tenant_id(payload: Dict) -> int:
        tid = payload.get("tenant_id")
        try:
            return int(tid) if tid is not None else 1
        except (TypeError, ValueError):
            return 1

    def _get_sync(self, tenant_id: int) -> IncrementalSync:
        if tenant_id not in self._sync_cache:
            self._sync_cache[tenant_id] = IncrementalSync(tenant_id=tenant_id)
        return self._sync_cache[tenant_id]

    def _load_registry_entry(self, source_id: str, table_name: str) -> Optional[Dict]:
        with self.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT central_table, column_map, pk_columns, schema_version,
                       unknown_columns, status
                  FROM cdc_table_registry
                 WHERE source_id = :sid AND table_name = :tbl
            """), {"sid": source_id, "tbl": table_name}).fetchone()
        if not row:
            return None
        return {
            "central_table": row[0],
            "column_map": row[1],
            "pk_columns": row[2],
            "schema_version": row[3],
            "unknown_columns": row[4],
            "status": row[5],
        }

    # ── status transitions ───────────────────────────────────────────────────
    def _mark_done(self, row_id: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE cdc_inbox
                   SET status='done', processed_at=now(),
                       last_error=NULL, last_error_class=NULL
                 WHERE id = :id
            """), {"id": row_id})

    def _mark_retry(self, row_id: int, error_class: str, detail: str, delay_ms: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(f"""
                UPDATE cdc_inbox
                   SET status='pending',
                       next_attempt_at = now() + INTERVAL '{int(delay_ms)} milliseconds',
                       last_error      = :detail,
                       last_error_class = :ec,
                       claimed_at      = NULL,
                       claimed_by      = NULL
                 WHERE id = :id
            """), {"id": row_id, "detail": detail[:8000], "ec": error_class})

    def _park_row(self, row_id: int, error_class: str, detail: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE cdc_inbox
                   SET status='parked',
                       last_error      = :detail,
                       last_error_class = :ec
                 WHERE id = :id
            """), {"id": row_id, "detail": detail[:8000], "ec": error_class})

    def _dlq_row(self, row: Dict, error_class: str, detail: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO cdc_dead_letter
                    (source_id, change_id, source_seq, table_name, op,
                     pk, payload, payload_before, schema_version,
                     error_class, error_detail, attempts)
                VALUES
                    (:sid, :cid, :seq, :tbl, :op,
                     CAST(:pk AS JSONB), CAST(:payload AS JSONB),
                     CAST(:payload_before AS JSONB), :sv,
                     :ec, :ed, :att)
                ON CONFLICT (source_id, change_id) DO NOTHING
            """), {
                "sid": row["source_id"],
                "cid": int(row["change_id"]),
                "seq": int(row["source_seq"]),
                "tbl": row["table_name"],
                "op": row["op"],
                "pk": json.dumps(row.get("pk") or {}),
                "payload": json.dumps(row.get("payload") or {}),
                "payload_before": json.dumps(row.get("payload_before"))
                                  if row.get("payload_before") is not None else None,
                "sv": int(row.get("schema_version") or 1),
                "ec": error_class,
                "ed": detail[:8000],
                "att": int(row.get("attempts") or 1),
            })
            conn.execute(text("""
                UPDATE cdc_inbox
                   SET status='failed', processed_at = now(),
                       last_error = :detail, last_error_class = :ec
                 WHERE id = :id
            """), {"id": row["id"], "detail": detail[:8000], "ec": error_class})

    def _exceeds_fk_wait(self, row_id: int) -> bool:
        secs = int(self.FK_MAX_WAIT_SECONDS)
        with self.engine.connect() as conn:
            row = conn.execute(text(f"""
                SELECT received_at < now() - INTERVAL '{secs} seconds'
                  FROM cdc_inbox WHERE id = :id
            """), {"id": row_id}).fetchone()
        return bool(row and row[0])
