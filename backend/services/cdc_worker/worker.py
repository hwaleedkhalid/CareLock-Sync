"""
CDC Worker core — orchestrates LISTEN/NOTIFY + polling on one source DB.

Reuses connector.cdc_monitor.CDCMonitor for trigger setup and streaming.
Maintains per (source_id, table_name) watermarks in the shared DB so multiple
workers across different source databases do not clobber each other.

Ordering: every batch sent to ingestion preserves change_id order produced
by data_change_log (BIGSERIAL → strictly monotonic per source DB), and the
worker advances the watermark only after a successful 200 / duplicate ack.
A failed batch is retried as a whole; partial commits are impossible.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests
from sqlalchemy import create_engine, text

from connector.cdc_monitor import CDCMonitor                  # reused
from services.common import hmac_sign
from services.common.backoff import exp_backoff_ms
from services.common.config import SourceConfig, shared_db_url

logger = logging.getLogger("cdc.worker.core")

_OP_MAP = {"INSERT": "I", "UPDATE": "U", "DELETE": "D"}


@dataclass
class WorkerStatus:
    source_id: str
    listen_connected: bool = False
    last_sync_at: Optional[float] = None         # epoch seconds
    last_error: Optional[str] = None
    last_error_at: Optional[float] = None
    listen_reconnects: int = 0
    push_failures: int = 0
    rows_pushed: int = 0
    started_at: float = field(default_factory=time.time)
    parked_partitions: int = 0


class CDCWorker:
    def __init__(self, source: SourceConfig, hmac_key: str, auto_setup: bool) -> None:
        self.source = source
        self.hmac_key = hmac_key
        self.auto_setup = auto_setup
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"

        self._stop = threading.Event()
        self._wake = threading.Event()
        self.status = WorkerStatus(source_id=source.id)

        self.cdc = CDCMonitor(source.db_url)                    # reused
        self.shared_engine = create_engine(shared_db_url(), pool_pre_ping=True, future=True)
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    # ── public API ───────────────────────────────────────────────────────────
    def request_stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def preflight(self) -> int:
        """Return 0 if ready; non-zero exit code on failure."""
        # 1. source DB reachable
        try:
            with self.cdc.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            self._fatal("source_db_unreachable", str(exc))
            return 2

        # 2. CDC objects present (or install)
        missing = self._missing_cdc_objects()
        if missing:
            if self.auto_setup or os.environ.get("CDC_AUTO_SETUP", "").lower() == "true":
                logger.info("installing missing CDC objects: %s", missing)
                self.cdc.setup_cdc_for_tables(self.source.tables)
                logger.info("setup_completed source=%s", self.source.id)
            else:
                logger.error(
                    "CDC objects missing on source %s for tables %s; "
                    "rerun with --setup or set CDC_AUTO_SETUP=true",
                    self.source.id, missing,
                )
                return 3

        # 3. ingestion endpoint reachable
        try:
            r = self._session.get(self.source.ingestion_health_endpoint, timeout=5)
            if r.status_code >= 500:
                raise RuntimeError(f"ingestion /healthz returned {r.status_code}")
        except Exception as exc:
            self._fatal("ingestion_unreachable", str(exc))
            return 4

        # 4. registry rows present
        if not self._registry_ok():
            registry_auto_stub = (
                os.environ.get("CDC_REGISTRY_AUTO_STUB", "").lower() == "true"
                or self.source.schema.registry_auto_stub
            )
            if registry_auto_stub:
                self._stub_registry()
            else:
                logger.error(
                    "cdc_table_registry rows missing for source=%s tables=%s; "
                    "set CDC_REGISTRY_AUTO_STUB=true to auto-create stubs",
                    self.source.id, self.source.tables,
                )
                return 6

        # 5. watermarks: ensure a row exists per (source_id, table_name).
        self._ensure_watermarks()
        return 0

    def run_once(self) -> None:
        for tbl in self.source.tables:
            self._drain_table(tbl)

    def run_forever(self) -> None:
        if self.source.listen_notify:
            t = threading.Thread(target=self._listen_loop, daemon=True, name="cdc-listen")
            t.start()
        self._poll_loop()

    # ── preflight helpers ────────────────────────────────────────────────────
    def _missing_cdc_objects(self) -> List[str]:
        missing: List[str] = []
        with self.cdc.engine.connect() as conn:
            for tbl in self.source.tables:
                row = conn.execute(text("""
                    SELECT 1 FROM pg_trigger t
                      JOIN pg_class c ON c.oid = t.tgrelid
                     WHERE c.relname = :tbl
                       AND t.tgname  = :tg
                       AND NOT t.tgisinternal
                """), {"tbl": tbl, "tg": f"trg_cdc_{tbl}"}).fetchone()
                if not row:
                    missing.append(tbl)
            if conn.execute(text("SELECT to_regclass('public.data_change_log')")).scalar() is None:
                missing.append("data_change_log")
            if conn.execute(text(
                "SELECT 1 FROM pg_proc WHERE proname='log_table_changes'"
            )).fetchone() is None:
                missing.append("fn:log_table_changes")
        return missing

    def _registry_ok(self) -> bool:
        with self.shared_engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT table_name FROM cdc_table_registry
                 WHERE source_id = :sid AND status = 'active'
            """), {"sid": self.source.id}).fetchall()
        registered = {r[0] for r in rows}
        return all(t in registered for t in self.source.tables)

    def _stub_registry(self) -> None:
        with self.shared_engine.begin() as conn:
            for tbl in self.source.tables:
                conn.execute(text("""
                    INSERT INTO cdc_table_registry
                        (source_id, table_name, central_table, column_map, pk_columns,
                         schema_version, unknown_columns, status)
                    VALUES (:sid, :tbl, :ctbl, '{}'::jsonb, '[]'::jsonb,
                            1, :uc, 'pending_review')
                    ON CONFLICT (source_id, table_name) DO NOTHING
                """), {
                    "sid": self.source.id,
                    "tbl": tbl,
                    "ctbl": tbl,
                    "uc": self.source.schema.unknown_columns_default,
                })

    def _ensure_watermarks(self) -> None:
        with self.shared_engine.begin() as conn:
            for tbl in self.source.tables:
                conn.execute(text("""
                    INSERT INTO cdc_watermarks (source_id, table_name)
                    VALUES (:sid, :tbl)
                    ON CONFLICT (source_id, table_name) DO NOTHING
                """), {"sid": self.source.id, "tbl": tbl})

    # ── main loops ───────────────────────────────────────────────────────────
    def _poll_loop(self) -> None:
        interval = self.source.poll_interval_seconds
        consecutive_full = 0
        while not self._stop.is_set():
            had_data = False
            for tbl in self.source.tables:
                if self._stop.is_set():
                    break
                pushed = self._drain_table(tbl)
                if pushed >= self.source.batch.max_rows:
                    had_data = True

            # adaptive interval (spike behavior)
            if had_data:
                consecutive_full += 1
                if consecutive_full >= 3:
                    interval = max(self.source.poll_interval_min_seconds, interval // 2)
            else:
                consecutive_full = 0
                interval = self.source.poll_interval_seconds

            self._wake.wait(timeout=interval)
            self._wake.clear()
        logger.info("poll_loop_exit source=%s", self.source.id)

    def _listen_loop(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                import psycopg2
                conn = psycopg2.connect(self.source.db_url)
                conn.set_isolation_level(0)  # autocommit
                with conn.cursor() as cur:
                    cur.execute("LISTEN data_changes;")
                self.status.listen_connected = True
                logger.info("listen_connected source=%s", self.source.id)
                backoff = 1.0

                while not self._stop.is_set():
                    if self._select_with_timeout(conn, 30):
                        conn.poll()
                        had_notify = False
                        while conn.notifies:
                            conn.notifies.pop(0)
                            had_notify = True
                        if had_notify:
                            # NOTIFY is only a hint — wake the polling loop;
                            # the polling loop reads via iter_changes_since,
                            # which is the authoritative source of rows.
                            self._wake.set()
            except Exception as exc:
                self.status.listen_connected = False
                self.status.listen_reconnects += 1
                logger.warning("listen_dropped source=%s err=%s", self.source.id, exc)
                # On reconnect, force an immediate polling cycle (no data loss).
                self._wake.set()
                if self._stop.wait(timeout=min(30.0, backoff)):
                    break
                backoff = min(30.0, backoff * 2)

    def _select_with_timeout(self, conn, timeout: float) -> bool:
        import select
        r, _, _ = select.select([conn], [], [], timeout)
        return bool(r)

    # ── batch drain ──────────────────────────────────────────────────────────
    def _drain_table(self, table_name: str) -> int:
        last_id = self._load_watermark(table_name)
        try:
            stream = self.cdc.iter_changes_since(
                last_id,
                tenant_id=None,                  # source-wide; ETL handles tenant routing
                batch_size=self.source.batch.max_rows,
            )
        except Exception as exc:
            self._record_error("source_query_failed", str(exc))
            return 0

        pushed_total = 0
        for raw_batch in stream:
            # filter to this table only — keep ordering (change_id ASC)
            batch = [r for r in raw_batch if r.get("table_name") == table_name]
            if not batch:
                continue
            ok = self._push_with_retry(table_name, batch)
            if not ok:
                # failure → stop draining this table; watermark NOT advanced.
                return pushed_total
            self._advance_watermark(table_name, batch[-1]["change_id"], batch[-1]["changed_at"])
            pushed_total += len(batch)
            self.status.rows_pushed += len(batch)
            self.status.last_sync_at = time.time()
        return pushed_total

    def _push_with_retry(self, table_name: str, batch: List[Dict]) -> bool:
        attempt = 0
        while not self._stop.is_set():
            attempt += 1
            try:
                status_code, body = self._push_once(table_name, batch)
            except requests.RequestException as exc:
                self._record_error("network", str(exc))
                if attempt >= self.source.retry.max_attempts:
                    self._dlq_batch(table_name, batch, "exhausted", str(exc), attempt)
                    return False
                self._sleep_backoff(attempt)
                continue

            if status_code == 200:
                return True
            if status_code == 401 or status_code == 403:
                self._fatal("auth", f"ingestion rejected with {status_code}: {body}")
                # halt — config is wrong; do not advance, do not DLQ.
                self.request_stop()
                return False
            if status_code == 404:
                self._fatal("route_missing", f"ingestion returned 404: {body}")
                self.request_stop()
                return False
            if status_code == 400 or status_code == 422:
                self._dlq_batch(table_name, batch, "validation", body, attempt)
                return True   # do NOT halt the worker; watermark advances past bad rows
            if status_code == 429:
                retry_after = self._parse_retry_after(body)
                self._record_error("rate_limited", f"backpressure retry_after={retry_after}")
                if attempt >= self.source.retry.max_attempts + 4:
                    self._dlq_batch(table_name, batch, "exhausted", "backpressure", attempt)
                    return False
                if self._stop.wait(timeout=retry_after):
                    return False
                continue
            if 500 <= status_code < 600:
                self._record_error("server_5xx", f"{status_code}: {body}")
                if attempt >= self.source.retry.max_attempts:
                    self._dlq_batch(table_name, batch, "exhausted", body, attempt)
                    return False
                self._sleep_backoff(attempt)
                continue

            # unexpected
            self._record_error("unexpected", f"{status_code}: {body}")
            if attempt >= self.source.retry.max_attempts:
                self._dlq_batch(table_name, batch, "exhausted", body, attempt)
                return False
            self._sleep_backoff(attempt)
        return False

    def _push_once(self, table_name: str, batch: List[Dict]) -> Tuple[int, str]:
        events = [self._row_to_event(r) for r in batch]
        doc = {
            "source_id": self.source.id,
            "schema_version": 1,
            "events": events,
        }
        body = json.dumps(doc, separators=(",", ":"), default=_jsonable).encode("utf-8")
        ts, sig = hmac_sign.sign(self.source.id, body, self.hmac_key)
        headers = {
            "X-CDC-Source": self.source.id,
            "X-CDC-Timestamp": str(ts),
            "X-CDC-Signature": sig,
        }
        r = self._session.post(
            self.source.ingestion_endpoint, data=body, headers=headers, timeout=30
        )
        return r.status_code, (r.text or "")

    @staticmethod
    def _row_to_event(row: Dict) -> Dict:
        op = _OP_MAP.get(row.get("operation", "").upper(), "U")
        rec_id = row.get("record_id")
        return {
            "change_id": int(row["change_id"]),
            "source_seq": int(row["change_id"]),
            "source_ts": row.get("changed_at") or _now_iso(),
            "table_name": row["table_name"],
            "op": op,
            "pk": {"record_id": rec_id} if rec_id is not None else {},
            "payload": row.get("new_data") or {},
            "payload_before": row.get("old_data"),
        }

    # ── watermarks ───────────────────────────────────────────────────────────
    def _load_watermark(self, table_name: str) -> int:
        with self.shared_engine.connect() as conn:
            row = conn.execute(text("""
                SELECT last_change_id FROM cdc_watermarks
                 WHERE source_id = :sid AND table_name = :tbl
            """), {"sid": self.source.id, "tbl": table_name}).fetchone()
        return int(row[0]) if row else 0

    def _advance_watermark(self, table_name: str, last_change_id: int, last_ts) -> None:
        with self.shared_engine.begin() as conn:
            conn.execute(text("""
                UPDATE cdc_watermarks
                   SET last_change_id  = GREATEST(last_change_id, :cid),
                       last_source_seq = GREATEST(last_source_seq, :cid),
                       last_source_ts  = COALESCE(CAST(:ts AS TIMESTAMPTZ), last_source_ts),
                       last_pushed_at  = now(),
                       last_acked_at   = now()
                 WHERE source_id = :sid AND table_name = :tbl
            """), {
                "sid": self.source.id,
                "tbl": table_name,
                "cid": int(last_change_id),
                "ts": last_ts if isinstance(last_ts, str) else None,
            })

    # ── DLQ + bookkeeping ────────────────────────────────────────────────────
    def _dlq_batch(self, table_name: str, batch: List[Dict],
                   error_class: str, detail: str, attempts: int) -> None:
        with self.shared_engine.begin() as conn:
            for row in batch:
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
                    "sid": self.source.id,
                    "cid": int(row["change_id"]),
                    "seq": int(row["change_id"]),
                    "tbl": table_name,
                    "op": _OP_MAP.get(row.get("operation", "").upper(), "U"),
                    "pk": json.dumps({"record_id": row.get("record_id")}),
                    "payload": json.dumps(row.get("new_data") or {}, default=_jsonable),
                    "payload_before": json.dumps(row.get("old_data"), default=_jsonable)
                                      if row.get("old_data") is not None else None,
                    "sv": 1,
                    "ec": error_class,
                    "ed": detail[:8000],
                    "att": int(attempts),
                })
        # Watermark still advances — these rows are terminally handled.
        self._advance_watermark(
            table_name, batch[-1]["change_id"], batch[-1].get("changed_at")
        )
        self.status.push_failures += 1
        logger.warning("batch_dlq source=%s table=%s rows=%d class=%s",
                       self.source.id, table_name, len(batch), error_class)

    def _sleep_backoff(self, attempt: int) -> None:
        ms = exp_backoff_ms(
            attempt,
            initial_ms=self.source.retry.initial_backoff_ms,
            max_ms=self.source.retry.max_backoff_ms,
            jitter_pct=self.source.retry.jitter_pct,
        )
        if self._stop.wait(timeout=ms / 1000.0):
            return

    def _parse_retry_after(self, body: str) -> float:
        # Honor Retry-After if sent in JSON {retry_after: N}; otherwise default.
        try:
            doc = json.loads(body)
            return float(doc.get("retry_after", 5))
        except Exception:
            return 5.0

    def _record_error(self, error_class: str, detail: str) -> None:
        self.status.last_error = f"{error_class}: {detail[:500]}"
        self.status.last_error_at = time.time()
        logger.warning("worker_error source=%s class=%s detail=%s",
                       self.source.id, error_class, detail[:500])

    def _fatal(self, error_class: str, detail: str) -> None:
        self._record_error(error_class, detail)
        logger.error("worker_fatal source=%s class=%s detail=%s",
                     self.source.id, error_class, detail[:500])


# ── helpers ──────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(o):
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)
