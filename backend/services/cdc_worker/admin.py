"""
CDC Worker admin server — /healthz and /metrics on a tiny stdlib HTTP server.

Avoids dragging FastAPI into the worker process. Single responder thread
serves both endpoints; failures here must never crash the worker.
"""
from __future__ import annotations

import json
import logging
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

logger = logging.getLogger("cdc.worker.admin")

if TYPE_CHECKING:
    from services.cdc_worker.worker import CDCWorker


def start_admin_server(*, port: int, worker: "CDCWorker") -> None:
    handler = _make_handler(worker)
    try:
        srv = HTTPServer(("0.0.0.0", port), handler)
    except OSError as exc:
        logger.warning("admin server failed to bind :%d (%s) — running without it",
                       port, exc)
        return
    logger.info("admin server listening on :%d", port)
    try:
        srv.serve_forever()
    except Exception as exc:
        logger.warning("admin server stopped: %s", exc)


def _make_handler(worker: "CDCWorker"):

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default access log
            return

        def do_GET(self):  # noqa: N802
            if self.path.startswith("/healthz"):
                return self._respond_health()
            if self.path.startswith("/metrics"):
                return self._respond_metrics()
            self.send_error(404)

        def _respond_health(self):
            s = worker.status
            now = time.time()
            stale = (now - s.last_sync_at) > (2 * worker.source.poll_interval_seconds) \
                if s.last_sync_at else False
            payload = {
                "status": "degraded" if stale or s.last_error else "ok",
                "source_id": s.source_id,
                "worker_id": worker.worker_id,
                "listen_connected": s.listen_connected,
                "last_sync_at": s.last_sync_at,
                "last_error": s.last_error,
                "last_error_at": s.last_error_at,
                "listen_reconnects": s.listen_reconnects,
                "rows_pushed": s.rows_pushed,
                "push_failures": s.push_failures,
                "started_at": s.started_at,
                "stale": stale,
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _respond_metrics(self):
            s = worker.status
            sid = s.source_id
            lines = [
                "# HELP cdc_worker_rows_pushed_total Rows successfully pushed",
                "# TYPE cdc_worker_rows_pushed_total counter",
                f'cdc_worker_rows_pushed_total{{source_id="{sid}"}} {s.rows_pushed}',
                "# HELP cdc_worker_push_failures_total Push failures",
                "# TYPE cdc_worker_push_failures_total counter",
                f'cdc_worker_push_failures_total{{source_id="{sid}"}} {s.push_failures}',
                "# HELP cdc_worker_listen_reconnects_total LISTEN reconnects",
                "# TYPE cdc_worker_listen_reconnects_total counter",
                f'cdc_worker_listen_reconnects_total{{source_id="{sid}"}} {s.listen_reconnects}',
                "# HELP cdc_worker_last_sync_timestamp_seconds Unix seconds of last successful push",
                "# TYPE cdc_worker_last_sync_timestamp_seconds gauge",
                f'cdc_worker_last_sync_timestamp_seconds{{source_id="{sid}"}} {s.last_sync_at or 0}',
                "# HELP cdc_worker_listen_connected 1 if LISTEN socket open",
                "# TYPE cdc_worker_listen_connected gauge",
                f'cdc_worker_listen_connected{{source_id="{sid}"}} {1 if s.listen_connected else 0}',
                "",
            ]
            body = "\n".join(lines).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler
