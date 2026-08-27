"""
POST /api/v1/cdc/ingest — accepts a batch of change events from a CDC Worker.

Request body (JSON):
{
  "source_id": "hospital_a",
  "schema_version": 1,
  "events": [
    {
      "change_id": 12345,
      "source_seq": 12345,
      "source_ts": "2026-04-25T10:00:00Z",
      "table_name": "patients",
      "op": "I",
      "pk": {"patient_id": 42},
      "payload": {...},
      "payload_before": {...}    // optional
    },
    ...
  ]
}

Headers:
  X-CDC-Source     : source_id (must match body)
  X-CDC-Timestamp  : unix seconds
  X-CDC-Signature  : hex sha256-hmac of (source_id + "." + ts + "." + body)

Response:
  200 {"accepted": N, "duplicate": M, "parked": K}
  400 {"error": "validation", "detail": "..."}
  401 {"error": "unauthorized"}
  413 {"error": "too_large"}
  429 {"error": "backpressure", "retry_after": 30}
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text

from services.common import hmac_sign

logger = logging.getLogger("cdc.ingestion.routes")

_VALID_OPS = {"I", "U", "D"}
_MAX_BODY_BYTES = 8 * 1024 * 1024                 # 8 MB hard cap
_BACKPRESSURE_THRESHOLD = int(
    os.environ.get("INGESTION_BACKPRESSURE_THRESHOLD", "100000")
)


def build_router(app: FastAPI) -> APIRouter:
    router = APIRouter(prefix="/api/v1/cdc", tags=["cdc"])
    engine = create_engine(app.state.db_url, pool_pre_ping=True, future=True)

    @router.post("/ingest")
    async def ingest(request: Request) -> Response:
        t0 = time.perf_counter()
        body = await request.body()
        if len(body) > _MAX_BODY_BYTES:
            return _err(app, "unknown", "too_large", 413, t0,
                        f"body {len(body)}B exceeds {_MAX_BODY_BYTES}B")

        # ── auth ──────────────────────────────────────────────────────────
        src_hdr = request.headers.get("X-CDC-Source", "")
        ts_hdr = request.headers.get("X-CDC-Timestamp", "")
        sig_hdr = request.headers.get("X-CDC-Signature", "")
        if not (src_hdr and ts_hdr and sig_hdr):
            return _err(app, src_hdr or "unknown", "unauthorized", 401, t0,
                        "missing CDC headers")

        try:
            ts_int = int(ts_hdr)
        except ValueError:
            return _err(app, src_hdr, "unauthorized", 401, t0, "bad timestamp")

        keys: Dict[str, str] = app.state.hmac_keys
        key = keys.get(src_hdr)
        if not key:
            return _err(app, src_hdr, "unauthorized", 401, t0, "unknown source")

        if not hmac_sign.verify(src_hdr, body, key, ts_int, sig_hdr):
            return _err(app, src_hdr, "unauthorized", 401, t0, "bad signature")

        # ── parse ─────────────────────────────────────────────────────────
        try:
            doc = json.loads(body)
        except json.JSONDecodeError as e:
            return _err(app, src_hdr, "invalid", 400, t0, f"json: {e}")

        if not isinstance(doc, dict):
            return _err(app, src_hdr, "invalid", 400, t0, "body must be object")
        if doc.get("source_id") != src_hdr:
            return _err(app, src_hdr, "invalid", 400, t0, "source_id mismatch")

        events = doc.get("events")
        if not isinstance(events, list) or not events:
            return _err(app, src_hdr, "invalid", 400, t0, "events must be non-empty list")

        schema_version = int(doc.get("schema_version", 1))

        # ── backpressure ──────────────────────────────────────────────────
        try:
            with engine.connect() as conn:
                pending = conn.execute(
                    text("SELECT count(*) FROM cdc_inbox WHERE status = 'pending'")
                ).scalar() or 0
        except Exception as exc:
            return _err(app, src_hdr, "error", 500, t0, f"db: {exc}")

        if pending >= _BACKPRESSURE_THRESHOLD:
            response = JSONResponse(
                {"error": "backpressure", "retry_after": 30, "pending": pending},
                status_code=429,
            )
            response.headers["Retry-After"] = "30"
            _record(app, src_hdr, "rate_limited", "backpressure", t0)
            return response

        # ── validate + classify per event ─────────────────────────────────
        try:
            registry = _load_registry(engine, src_hdr)
        except Exception as exc:
            return _err(app, src_hdr, "error", 500, t0, f"registry: {exc}")

        prepared: List[Dict[str, Any]] = []
        new_table_audits: List[Tuple[str, str]] = []   # (table_name, reason)
        invalid_reason = None

        for ev in events:
            err = _validate_event(ev)
            if err:
                invalid_reason = err
                break
            tbl = ev["table_name"]
            entry = registry.get(tbl)
            policy_status = "pending"
            if entry is None:
                # Schema evolution Case 3 — new table.
                new_table_policy = os.environ.get(
                    "CDC_NEW_TABLE_POLICY", "require_config"
                )
                if new_table_policy == "ignore":
                    new_table_audits.append((tbl, "ignored_new_table"))
                    continue
                elif new_table_policy == "auto_register":
                    _auto_register_stub(engine, src_hdr, tbl)
                    registry = _load_registry(engine, src_hdr)
                    policy_status = "parked"
                    new_table_audits.append((tbl, "auto_registered"))
                else:  # require_config (default)
                    policy_status = "parked"
                    new_table_audits.append((tbl, "unknown_table"))
            else:
                # Case 1 — unknown columns: keep raw payload; we never crash.
                # Detection done by registry.unknown_columns at ETL time.
                if entry.get("status") in ("paused", "pending_review"):
                    policy_status = "parked"
            prepared.append({
                "source_id": src_hdr,
                "change_id": int(ev["change_id"]),
                "source_seq": int(ev["source_seq"]),
                "source_ts": ev["source_ts"],
                "table_name": tbl,
                "op": ev["op"],
                "pk": json.dumps(ev["pk"]),
                "payload": json.dumps(ev["payload"]),
                "payload_before": json.dumps(ev.get("payload_before"))
                                  if ev.get("payload_before") is not None else None,
                "schema_version": schema_version,
                "status": policy_status,
            })

        if invalid_reason:
            return _err(app, src_hdr, "invalid", 400, t0, invalid_reason)

        # ── persist atomically ────────────────────────────────────────────
        try:
            accepted, duplicate = _insert_events(engine, prepared)
            for tbl, reason in new_table_audits:
                _audit(engine, src_hdr, tbl, "new_table", {"reason": reason})
        except Exception as exc:
            return _err(app, src_hdr, "error", 500, t0, f"db: {exc}")

        parked = sum(1 for r in prepared if r["status"] == "parked")
        _record(app, src_hdr, "accepted", None, t0)
        return JSONResponse(
            {"accepted": accepted, "duplicate": duplicate, "parked": parked},
            status_code=200,
        )

    return router


# ── helpers ─────────────────────────────────────────────────────────────────
def _validate_event(ev: Any) -> str | None:
    if not isinstance(ev, dict):
        return "event must be object"
    for key in ("change_id", "source_seq", "source_ts", "table_name", "op", "pk", "payload"):
        if key not in ev:
            return f"missing field {key!r}"
    if ev["op"] not in _VALID_OPS:
        return f"invalid op {ev['op']!r}"
    if not isinstance(ev["pk"], dict):
        return "pk must be object"
    if not isinstance(ev["payload"], dict):
        return "payload must be object"
    return None


def _load_registry(engine, source_id: str) -> Dict[str, Dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT table_name, central_table, column_map, pk_columns,
                   schema_version, unknown_columns, status
              FROM cdc_table_registry
             WHERE source_id = :sid
        """), {"sid": source_id}).fetchall()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        out[r[0]] = {
            "central_table": r[1],
            "column_map": r[2],
            "pk_columns": r[3],
            "schema_version": r[4],
            "unknown_columns": r[5],
            "status": r[6],
        }
    return out


def _auto_register_stub(engine, source_id: str, table_name: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO cdc_table_registry
                (source_id, table_name, central_table, column_map, pk_columns,
                 schema_version, unknown_columns, status)
            VALUES (:sid, :tbl, :ctbl, '{}'::jsonb, '[]'::jsonb,
                    1, 'store_raw', 'pending_review')
            ON CONFLICT (source_id, table_name) DO NOTHING
        """), {"sid": source_id, "tbl": table_name, "ctbl": table_name})


def _insert_events(engine, rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    if not rows:
        return 0, 0
    accepted = 0
    duplicate = 0
    with engine.begin() as conn:
        for r in rows:
            res = conn.execute(text("""
                INSERT INTO cdc_inbox
                    (source_id, change_id, source_seq, source_ts, table_name,
                     op, pk, payload, payload_before, schema_version, status)
                VALUES
                    (:source_id, :change_id, :source_seq, :source_ts, :table_name,
                     :op, CAST(:pk AS JSONB), CAST(:payload AS JSONB),
                     CAST(:payload_before AS JSONB), :schema_version, :status)
                ON CONFLICT (source_id, change_id) DO NOTHING
                RETURNING id
            """), r)
            if res.fetchone() is None:
                duplicate += 1
            else:
                accepted += 1
    return accepted, duplicate


def _audit(engine, source_id: str, table_name: str, event: str, detail: dict) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO cdc_schema_audit (source_id, table_name, event, detail)
                VALUES (:sid, :tbl, :ev, CAST(:d AS JSONB))
            """), {"sid": source_id, "tbl": table_name,
                   "ev": event, "d": json.dumps(detail)})
    except Exception as exc:   # audit must never break ingestion
        logger.warning("audit insert failed: %s", exc)


def _record(app: FastAPI, source_id: str, result: str,
            error_class: str | None, t0: float) -> None:
    duration_ms = (time.perf_counter() - t0) * 1000.0
    app.state.metrics.observe(
        source_id=source_id, result=result,
        error_class=error_class, duration_ms=duration_ms,
    )


def _err(app: FastAPI, source_id: str, result: str,
         status_code: int, t0: float, detail: str) -> Response:
    _record(app, source_id, result, result, t0)
    return JSONResponse({"error": result, "detail": detail}, status_code=status_code)
