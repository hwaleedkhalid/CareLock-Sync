"""
Apply the shared-DB schema (cdc_inbox, cdc_dead_letter, cdc_watermarks,
cdc_control_jobs, cdc_table_registry, cdc_schema_audit).

Idempotent — run on every service start.
"""
from __future__ import annotations

import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sql", "schema.sql")


def _load_schema_sql() -> str:
    with open(_SCHEMA_FILE, "r", encoding="utf-8") as fh:
        return fh.read()


def apply_schema(engine_or_url) -> None:
    """Apply the full schema. Safe to call on every startup."""
    if isinstance(engine_or_url, str):
        engine: Engine = create_engine(engine_or_url, pool_pre_ping=True)
        own_engine = True
    else:
        engine = engine_or_url
        own_engine = False
    sql = _load_schema_sql()
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
        logger.info("CDC schema applied (%s)", _SCHEMA_FILE)
    finally:
        if own_engine:
            engine.dispose()
