"""
MySQL Adapter — full operational + trigger-based CDC support.

Connection-string forms accepted by ``CDCAdapterFactory``:
    mysql://user:pass@host:port/dbname
    mysql+pymysql://user:pass@host:port/dbname

CDC strategy
------------
MySQL has native binlog-based CDC, but consuming it requires REPLICATION
SLAVE privileges and a properly tuned server.  For the project's
hospital-database scenario we use the same trigger-and-change-log pattern
the PostgreSQL adapter uses, mirrored into MySQL syntax:

  * ``data_change_log`` table (BIGINT auto-increment PK + JSON columns)
  * one trigger per table (INSERT, UPDATE, DELETE) writing to it
  * polled by ``get_changes`` via ``change_id > :since`` selector

This keeps the contract identical to PostgreSQLAdapter and works against
the stock ``mysql:8.0`` Docker image with no privileged configuration.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlparse

from sqlalchemy import create_engine, text, inspect as sa_inspect
from sqlalchemy.engine import Engine

from cdc.base_adapter import CDCAdapter, ChangeEvent, OperationType

logger = logging.getLogger(__name__)


def _to_sqlalchemy_url(connection_string: str) -> str:
    """Promote ``mysql://`` → ``mysql+pymysql://`` so SQLAlchemy can connect."""
    if connection_string.startswith("mysql://"):
        return "mysql+pymysql://" + connection_string[len("mysql://"):]
    return connection_string


class MySQLAdapter(CDCAdapter):
    """MySQL trigger-based CDC + ETL adapter."""

    SUPPORTS_NATIVE_CDC = True   # via binlog (not used — trigger path here)
    SUPPORTS_TRANSACTIONS = True

    CHANGE_LOG_DDL = """
        CREATE TABLE IF NOT EXISTS data_change_log (
            change_id   BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
            table_name  VARCHAR(100) NOT NULL,
            operation   VARCHAR(10)  NOT NULL,
            record_id   VARCHAR(255),
            old_data    JSON,
            new_data    JSON,
            changed_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_name   VARCHAR(100),
            tenant_id   INT,
            INDEX idx_change_id (change_id),
            INDEX idx_table     (table_name),
            INDEX idx_changed   (changed_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """

    # ── construction ─────────────────────────────────────────────────────────
    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self.sqlalchemy_url = _to_sqlalchemy_url(connection_string)
        self._engine: Optional[Engine] = None

    # ── identity ─────────────────────────────────────────────────────────────
    def get_database_type(self) -> str:
        return "mysql"

    # ── connection lifecycle ─────────────────────────────────────────────────
    def connect(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(
                self.sqlalchemy_url,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        return self._engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    @property
    def engine(self) -> Engine:
        return self.connect()

    def validate_connection(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.warning("MySQL connection validation failed: %s", exc)
            return False

    # ── schema introspection ─────────────────────────────────────────────────
    def fetch_schema(self) -> Dict[str, Any]:
        inspector = sa_inspect(self.engine)
        tables: Dict[str, Any] = {}

        for tname in inspector.get_table_names():
            cols = []
            for col in inspector.get_columns(tname):
                cols.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "primary_key": col.get("primary_key", False),
                    "default": str(col.get("default")) if col.get("default") else None,
                })

            try:
                with self.engine.connect() as conn:
                    row_count = conn.execute(
                        text(f"SELECT COUNT(*) FROM `{tname}`")
                    ).scalar()
            except Exception:
                row_count = None

            tables[tname] = {
                "table_name":   tname,
                "columns":      cols,
                "primary_keys": inspector.get_pk_constraint(tname).get(
                                    "constrained_columns", []),
                "foreign_keys": [{
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table":      fk["referred_table"],
                    "referred_columns":    fk["referred_columns"],
                } for fk in inspector.get_foreign_keys(tname)],
                "row_count":    row_count,
            }

        return {
            "database_type": "mysql",
            "database":      _db_name(self.sqlalchemy_url),
            "discovered_at": datetime.utcnow().isoformat(),
            "total_tables":  len(tables),
            "tables":        tables,
        }

    # ── data extraction ──────────────────────────────────────────────────────
    def extract_data(
        self,
        table_name: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        self._assert_table_exists(table_name)
        sql = f"SELECT * FROM `{table_name}`"
        params: Dict[str, Any] = {}
        if limit is not None:
            sql += " LIMIT :lim OFFSET :off"
            params = {"lim": int(limit), "off": int(offset)}
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]

    def iter_data(
        self,
        table_name: str,
        batch_size: int = 500,
    ) -> Iterator[List[Dict[str, Any]]]:
        # Server-side streaming using PyMySQL's SSCursor would be ideal, but
        # offset-paging is portable and adequate for the Docker scenarios.
        offset = 0
        while True:
            batch = self.extract_data(table_name, limit=batch_size, offset=offset)
            if not batch:
                return
            yield batch
            if len(batch) < batch_size:
                return
            offset += batch_size

    # ── data load ────────────────────────────────────────────────────────────
    def load_data(
        self,
        table_name: str,
        rows: List[Dict[str, Any]],
        upsert_keys: Optional[List[str]] = None,
    ) -> int:
        if not rows:
            return 0
        self._assert_table_exists(table_name)
        cols = list(rows[0].keys())
        col_csv = ", ".join(f"`{c}`" for c in cols)
        param_csv = ", ".join(f":{c}" for c in cols)

        if upsert_keys:
            non_key = [c for c in cols if c not in upsert_keys]
            update_clause = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in non_key) \
                            or f"`{cols[0]}`=VALUES(`{cols[0]}`)"
            sql = (f"INSERT INTO `{table_name}` ({col_csv}) "
                   f"VALUES ({param_csv}) "
                   f"ON DUPLICATE KEY UPDATE {update_clause}")
        else:
            sql = f"INSERT INTO `{table_name}` ({col_csv}) VALUES ({param_csv})"

        written = 0
        with self.engine.begin() as conn:
            for r in rows:
                conn.execute(text(sql), r)
                written += 1
        return written

    # ── CDC setup ────────────────────────────────────────────────────────────
    def setup_cdc(self, tables: List[str]) -> bool:
        try:
            with self.engine.begin() as conn:
                conn.execute(text(self.CHANGE_LOG_DDL))

            inspector = sa_inspect(self.engine)
            valid = set(inspector.get_table_names())
            for table in tables:
                if table not in valid:
                    logger.warning("MySQL CDC: skipping unknown table %s", table)
                    continue
                self._install_triggers(table, inspector)

            self.is_setup = True
            return True
        except Exception as exc:
            logger.error("MySQL CDC setup failed: %s", exc, exc_info=True)
            return False

    def _install_triggers(self, table: str, inspector) -> None:
        pk_cols = inspector.get_pk_constraint(table).get("constrained_columns", [])
        pk_col = pk_cols[0] if pk_cols else "id"
        col_names = [c["name"] for c in inspector.get_columns(table)]

        # JSON_OBJECT('col', NEW.col, ...) — assemble for OLD/NEW dynamically
        def _json(prefix: str) -> str:
            parts = ", ".join(f"'{c}', {prefix}.`{c}`" for c in col_names)
            return f"JSON_OBJECT({parts})" if parts else "JSON_OBJECT()"

        new_obj = _json("NEW")
        old_obj = _json("OLD")

        with self.engine.begin() as conn:
            # MySQL 8 cannot CREATE OR REPLACE triggers; drop-then-create.
            for op, body in [
                ("INSERT",
                 f"INSERT INTO data_change_log (table_name, operation, record_id, new_data) "
                 f"VALUES ('{table}', 'INSERT', NEW.`{pk_col}`, {new_obj});"),
                ("UPDATE",
                 f"INSERT INTO data_change_log (table_name, operation, record_id, old_data, new_data) "
                 f"VALUES ('{table}', 'UPDATE', NEW.`{pk_col}`, {old_obj}, {new_obj});"),
                ("DELETE",
                 f"INSERT INTO data_change_log (table_name, operation, record_id, old_data) "
                 f"VALUES ('{table}', 'DELETE', OLD.`{pk_col}`, {old_obj});"),
            ]:
                trig = f"{table}_cdc_{op.lower()}"
                conn.execute(text(f"DROP TRIGGER IF EXISTS `{trig}`"))
                conn.execute(text(
                    f"CREATE TRIGGER `{trig}` AFTER {op} ON `{table}` "
                    f"FOR EACH ROW {body}"
                ))
        logger.info("MySQL CDC triggers installed for %s", table)

    # ── change retrieval ─────────────────────────────────────────────────────
    def get_changes(
        self,
        since_change_id: Optional[int] = None,
        table_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[ChangeEvent]:
        sql = ("SELECT change_id, table_name, operation, record_id, "
               "old_data, new_data, changed_at "
               "FROM data_change_log WHERE 1=1")
        params: Dict[str, Any] = {}
        if since_change_id is not None:
            sql += " AND change_id > :sid"; params["sid"] = since_change_id
        if table_name:
            sql += " AND table_name = :tname"; params["tname"] = table_name
        sql += " ORDER BY change_id LIMIT :lim"; params["lim"] = int(limit)

        events: List[ChangeEvent] = []
        try:
            with self.engine.connect() as conn:
                for row in conn.execute(text(sql), params):
                    events.append(ChangeEvent(
                        change_id=row[0],
                        table_name=row[1],
                        operation=OperationType[row[2]],
                        record_id=row[3],
                        old_data=_load_json(row[4]),
                        new_data=_load_json(row[5]),
                        changed_at=row[6],
                        database_type="mysql",
                    ))
        except Exception as exc:
            logger.error("MySQL get_changes failed: %s", exc)
        return events

    def get_latest_change_id(self) -> Optional[int]:
        try:
            with self.engine.connect() as conn:
                return conn.execute(
                    text("SELECT MAX(change_id) FROM data_change_log")
                ).scalar()
        except Exception:
            return None

    def is_cdc_enabled(self, table_name: str) -> bool:
        try:
            with self.engine.connect() as conn:
                cnt = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.triggers "
                    "WHERE event_object_table = :t AND trigger_name LIKE :p"
                ), {"t": table_name, "p": f"{table_name}_cdc_%"}).scalar()
            return bool(cnt)
        except Exception:
            return False

    # ── helpers ──────────────────────────────────────────────────────────────
    def _assert_table_exists(self, table_name: str) -> None:
        valid = sa_inspect(self.engine).get_table_names()
        if table_name not in valid:
            raise ValueError(f"Unknown MySQL table: {table_name!r}. "
                             f"Available: {sorted(valid)}")


def _db_name(url: str) -> str:
    try:
        return urlparse(url).path.lstrip("/")
    except Exception:
        return ""


def _load_json(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {"_raw": str(value)}
