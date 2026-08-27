"""ETL Worker /healthz and /metrics on a stdlib HTTP server."""
from __future__ import annotations

import json
import logging
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

from sqlalchemy import text

logger = logging.getLogger("cdc.etl.admin")

if TYPE_CHECKING:
    from services.etl_worker.worker import ETLWorker


def start_admin_server(*, port: int, worker: "ETLWorker") -> None:
    handler = _make_handler(worker)
    try:
        srv = HTTPServer(("0.0.0.0", port), handler)
    except OSError as exc:
        logger.warning("admin server failed to bind :%d (%s) — running without it",
                       port, exc)
        return
    logger.info("etl admin listening on :%d", port)
    try:
        srv.serve_forever()
    except Exception as exc:
        logger.warning("etl admin stopped: %s", exc)


def _make_handler(worker: "ETLWorker"):

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def do_GET(self):  # noqa: N802
            if self.path.startswith("/healthz"):
                return self._respond_health()
            if self.path.startswith("/metrics"):
                return self._respond_metrics()
            self.send_error(404)

        def _respond_health(self):
            s = worker.status
            payload = {
                "status": "ok",
                "worker_id": s.worker_id,
                "current_partition": s.current_partition,
                "last_processed_at": s.last_processed_at,
                "last_error": s.last_error,
                "rows_done": s.rows_done,
                "rows_retried": s.rows_retried,
                "rows_dlq": s.rows_dlq,
                "rows_parked": s.rows_parked,
                "started_at": s.started_at,
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _respond_metrics(self):
            s = worker.status
            wid = s.worker_id
            lag_rows, lag_seconds = _query_lag(worker)
            lines = [
                "# HELP etl_worker_rows_done_total ETL rows processed successfully",
                "# TYPE etl_worker_rows_done_total counter",
                f'etl_worker_rows_done_total{{worker_id="{wid}"}} {s.rows_done}',
                "# HELP etl_worker_rows_retried_total ETL rows scheduled for retry",
                "# TYPE etl_worker_rows_retried_total counter",
                f'etl_worker_rows_retried_total{{worker_id="{wid}"}} {s.rows_retried}',
                "# HELP etl_worker_rows_dlq_total ETL rows moved to DLQ",
                "# TYPE etl_worker_rows_dlq_total counter",
                f'etl_worker_rows_dlq_total{{worker_id="{wid}"}} {s.rows_dlq}',
                "# HELP etl_worker_rows_parked_total ETL rows parked (schema drift)",
                "# TYPE etl_worker_rows_parked_total counter",
                f'etl_worker_rows_parked_total{{worker_id="{wid}"}} {s.rows_parked}',
                "# HELP etl_worker_queue_lag_rows Pending cdc_inbox rows",
                "# TYPE etl_worker_queue_lag_rows gauge",
                f"etl_worker_queue_lag_rows {lag_rows}",
                "# HELP etl_worker_queue_lag_seconds Age of oldest pending row in seconds",
                "# TYPE etl_worker_queue_lag_seconds gauge",
                f"etl_worker_queue_lag_seconds {lag_seconds:.1f}",
                "",
            ]
            body = "\n".join(lines).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _query_lag(worker) -> tuple[int, float]:
    try:
        with worker.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT count(*),
                       COALESCE(EXTRACT(EPOCH FROM now() - MIN(received_at)), 0)
                  FROM cdc_inbox WHERE status='pending'
            """)).fetchone()
        if not row:
            return 0, 0.0
        return int(row[0] or 0), float(row[1] or 0.0)
    except Exception:
        return 0, 0.0
