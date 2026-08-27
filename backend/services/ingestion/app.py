"""
CDC Ingestion Service — FastAPI app on port 8004.

Responsibilities:
  * Validate HMAC signature from CDC Worker.
  * Persist incoming change rows into cdc_inbox idempotently
    (UNIQUE (source_id, change_id)).
  * Apply the schema-evolution policy from cdc_table_registry:
    unknown tables and unknown columns are parked / audited / rejected
    according to per-source policy.
  * Expose /healthz and /metrics for observability.

Backpressure: returns 429 with Retry-After when cdc_inbox pending count
exceeds INGESTION_BACKPRESSURE_THRESHOLD.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from typing import Dict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

# path bootstrap so `services.common` and `backend.common` both resolve
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _BACKEND)

from services.common import config as cfg          # noqa: E402
from services.common.schema import apply_schema     # noqa: E402
from services.ingestion.routes import build_router  # noqa: E402

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("cdc.ingestion")

app = FastAPI(title="CareLock CDC Ingestion", version="1.0")


@app.on_event("startup")
def _startup() -> None:
    db_url = cfg.shared_db_url()
    apply_schema(db_url)
    keys = cfg.parse_hmac_keys()
    if not keys:
        logger.error("CDC_HMAC_KEYS is empty — refusing to start. "
                     "Set CDC_HMAC_KEYS=source_a:secret_a,...")
        raise RuntimeError("CDC_HMAC_KEYS not configured")
    logger.info("Loaded HMAC keys for sources: %s", sorted(keys))
    app.state.hmac_keys = keys
    app.state.db_url = db_url
    app.state.metrics = _Metrics()
    app.include_router(build_router(app))
    logger.info("Ingestion ready on shared DB; %d HMAC keys loaded", len(keys))


@app.get("/healthz")
def healthz() -> Dict:
    metrics = getattr(app.state, "metrics", None)
    return {
        "status": "ok",
        "db_ok": True,
        "hmac_keys_loaded": len(getattr(app.state, "hmac_keys", {}) or {}),
        "requests_total": metrics.total if metrics else 0,
        "requests_failed": metrics.failed if metrics else 0,
    }


@app.get("/metrics")
def metrics() -> Response:
    m: _Metrics = app.state.metrics
    body = m.render_prometheus()
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")


class _Metrics:
    """Tiny in-process counter store; renders a Prometheus exposition payload."""
    def __init__(self) -> None:
        self.total = 0
        self.failed = 0
        self.by_result: Dict[str, int] = {}     # result label → count
        self.by_error_class: Dict[str, int] = {}
        self.duration_sum_ms = 0.0
        self.duration_count = 0

    def observe(self, *, source_id: str, result: str,
                error_class: str | None, duration_ms: float) -> None:
        self.total += 1
        if result != "accepted" and result != "duplicate":
            self.failed += 1
        key = f"{source_id}|{result}"
        self.by_result[key] = self.by_result.get(key, 0) + 1
        if error_class:
            self.by_error_class[f"{source_id}|{error_class}"] = (
                self.by_error_class.get(f"{source_id}|{error_class}", 0) + 1
            )
        self.duration_sum_ms += duration_ms
        self.duration_count += 1

    def render_prometheus(self) -> str:
        lines = [
            "# HELP ingestion_requests_total CDC ingestion requests",
            "# TYPE ingestion_requests_total counter",
        ]
        for key, n in self.by_result.items():
            src, result = key.split("|", 1)
            lines.append(
                f'ingestion_requests_total{{source_id="{src}",result="{result}"}} {n}'
            )
        lines += [
            "# HELP ingestion_failures_total CDC ingestion failures by class",
            "# TYPE ingestion_failures_total counter",
        ]
        for key, n in self.by_error_class.items():
            src, ec = key.split("|", 1)
            lines.append(
                f'ingestion_failures_total{{source_id="{src}",error_class="{ec}"}} {n}'
            )
        avg_ms = (self.duration_sum_ms / self.duration_count) if self.duration_count else 0.0
        lines += [
            "# HELP ingestion_request_duration_ms Average request duration",
            "# TYPE ingestion_request_duration_ms gauge",
            f"ingestion_request_duration_ms {avg_ms:.3f}",
            "",
        ]
        return "\n".join(lines)
