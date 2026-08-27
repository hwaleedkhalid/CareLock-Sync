"""
SQL Server Adapter — pyodbc-backed full ETL + trigger-based CDC.

Connection-string forms accepted by ``CDCAdapterFactory``:
    sqlserver://user:pass@host:port/dbname
    mssql://user:pass@host:port/dbname
    mssql+pyodbc://...                    (already SQLAlchemy-native)

Notes on the Docker stack
-------------------------
``mcr.microsoft.com/mssql/server:2022-latest`` (Developer edition) DOES
ship native CDC, but enabling it requires SQL Agent + a privileged
database-level call (``sys.sp_cdc_enable_db``).  To keep the integration
test path simple and to mirror PostgreSQLAdapter's behaviour we use
trigger-based CDC against a ``data_change_log`` table.  Native CDC can
be added later by overriding ``setup_cdc`` in a subclass.

Driver
------
The Microsoft *ODBC Driver 17/18 for SQL Server* must be installed on
the host.  The adapter probes which is available; if neither is present
``connect()`` raises a clear, actionable error.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlparse, unquote, quote_plus

from sqlalchemy import create_engine, text, inspect as sa_inspect
from sqlalchemy.engine import Engine

from cdc.base_adapter import CDCAdapter, ChangeEvent, OperationType

logger = logging.getLogger(__name__)


_DRIVER_CANDIDATES = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
)


def _detect_odbc_driver() -> Optional[str]:
    try:
        import pyodbc  # local import — optional dep
    except ImportError:
        return None
    drivers = set(pyodbc.drivers())
    for d in _DRIVER_CANDIDATES:
        if d in drivers:
            return d
    return None


def _to_sqlalchemy_url(connection_string: str) -> str:
    """
    Translate ``sqlserver://user:pass@host:port/db`` to the verbose
    SQLAlchemy + pyodbc form.  Already-SQLAlchemy URLs pass through.
    """
    if connection_string.startswith("mssql+pyodbc://"):
        return connection_string

    # Accept either ``sqlserver://`` or ``mssql://`` prefixes
    cs = connection_string
    if cs.startswith("sqlserver://"):
        cs = "mssql://" + cs[len("sqlserver://"):]

    # urlparse mishandles passwords containing '@' so split first
    # Format: mssql://user:pass@host:port/db
    m = re.match(r"^mssql://([^:]+):(.+)@([^:/]+)(?::(\d+))?/(.+)$", cs)
    if not m:
        raise ValueError(
            f"Cannot parse SQL Server connection string: {connection_string!r}"
        )
    user, pwd, host, port, db = m.group(1), m.group(2), m.group(3), \
                                m.group(4) or "1433", m.group(5)

    driver = _detect_odbc_driver()
    if driver is None:
        raise ImportError(
            "SQL Server adapter requires the Microsoft ODBC Driver "
            "(17 or 18) for SQL Server. Install it from "
            "https://learn.microsoft.com/sql/connect/odbc/"
        )
    driver_q = driver.replace(" ", "+")
    # URL-encode user + password so '@' / ':' / '/' inside credentials don't
    # confuse SQLAlchemy's own URL parser when it round-trips the string.
    user_q = quote_plus(user)
    pwd_q  = quote_plus(unquote(pwd))
    return (f"mssql+pyodbc://{user_q}:{pwd_q}@{host}:{port}/{db}"
            f"?driver={driver_q}&TrustServerCertificate=yes&Encrypt=no")


class SQLServerAdapter(CDCAdapter):
    """SQL Server trigger-based CDC + ETL adapter."""

    SUPPORTS_NATIVE_CDC = True   # via sys.sp_cdc_enable_db (not used here)
    SUPPORTS_TRANSACTIONS = True

    CHANGE_LOG_DDL = """
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'data_change_log')
        BEGIN
            CREATE TABLE data_change_log (
                change_id   BIGINT IDENTITY(1,1) PRIMARY KEY,
                table_name  NVARCHAR(100) NOT NULL,
                operation   NVARCHAR(10)  NOT NULL,
                record_id   NVARCHAR(255),
                old_data    NVARCHAR(MAX),
                new_data    NVARCHAR(MAX),
                changed_at  DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                user_name   NVARCHAR(100) DEFAULT SUSER_SNAME(),
                tenant_id   INT
            );
            CREATE INDEX idx_change_log_id ON data_change_log(change_id);
            CREATE INDEX idx_change_log_tbl ON data_change_log(table_name);
        END
    """

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self.sqlalchemy_url = _to_sqlalchemy_url(connection_string)
        self._engine: Optional[Engine] = None

    # ── identity ─────────────────────────────────────────────────────────────
    def get_database_type(self) -> str:
        return "sqlserver"

    # ── connection lifecycle ─────────────────────────────────────────────────
    def connect(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(
                self.sqlalchemy_url,
                pool_pre_ping=True,
                fast_executemany=True,
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
            logger.warning("SQL Server connection validation failed: %s", exc)
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
                        text(f"SELECT COUNT(*) FROM [{tname}]")
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
            "database_type": "sqlserver",
            "discovered_at": datetime.utcnow().isoformat(),
            "total_tables":  len(tables),
            "tables":        tables,
        }

    # ── extract ──────────────────────────────────────────────────────────────
    def extract_data(
        self,
        table_name: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        self._assert_table_exists(table_name)
        # SQL Server requires ORDER BY for OFFSET/FETCH; fall back to TOP if no order needed.
        if limit is not None and offset > 0:
            inspector = sa_inspect(self.engine)
            pks = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
            order = pks[0] if pks else inspector.get_columns(table_name)[0]["name"]
            sql = (f"SELECT * FROM [{table_name}] ORDER BY [{order}] "
                   f"OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY")
            params = {"off": int(offset), "lim": int(limit)}
        elif limit is not None:
            sql = f"SELECT TOP {int(limit)} * FROM [{table_name}]"
            params = {}
        else:
            sql = f"SELECT * FROM [{table_name}]"
            params = {}

        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]

    # ── load ─────────────────────────────────────────────────────────────────
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
        col_csv = ", ".join(f"[{c}]" for c in cols)
        param_csv = ", ".join(f":{c}" for c in cols)

        if upsert_keys:
            on_clause = " AND ".join(f"T.[{k}] = S.[{k}]" for k in upsert_keys)
            non_key = [c for c in cols if c not in upsert_keys]
            update = ", ".join(f"T.[{c}] = S.[{c}]" for c in non_key) \
                     or f"T.[{cols[0]}] = S.[{cols[0]}]"
            insert_cols = ", ".join(f"[{c}]" for c in cols)
            insert_vals = ", ".join(f"S.[{c}]" for c in cols)
            select_cols = ", ".join(f":{c} AS [{c}]" for c in cols)
            sql = (f"MERGE [{table_name}] AS T "
                   f"USING (SELECT {select_cols}) AS S "
                   f"ON ({on_clause}) "
                   f"WHEN MATCHED THEN UPDATE SET {update} "
                   f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals});")
        else:
            sql = f"INSERT INTO [{table_name}] ({col_csv}) VALUES ({param_csv})"

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
                for stmt in self.CHANGE_LOG_DDL.strip().split(";"):
                    if stmt.strip():
                        conn.execute(text(stmt))

            inspector = sa_inspect(self.engine)
            valid = set(inspector.get_table_names())
            for table in tables:
                if table not in valid:
                    logger.warning("SQLServer CDC: skipping unknown table %s", table)
                    continue
                self._install_triggers(table, inspector)
            self.is_setup = True
            return True
        except Exception as exc:
            logger.error("SQL Server CDC setup failed: %s", exc, exc_info=True)
            return False

    def _install_triggers(self, table: str, inspector) -> None:
        pks = inspector.get_pk_constraint(table).get("constrained_columns", [])
        pk_col = pks[0] if pks else "id"
        trig = f"trg_{table}_cdc"

        # SQL Server's FOR JSON PATH gives a JSON serialisation of the rowset.
        body = f"""
        CREATE OR ALTER TRIGGER [{trig}] ON [{table}]
        AFTER INSERT, UPDATE, DELETE
        AS
        BEGIN
            SET NOCOUNT ON;
            DECLARE @op NVARCHAR(10);
            IF EXISTS (SELECT 1 FROM inserted) AND EXISTS (SELECT 1 FROM deleted)
                SET @op = 'UPDATE';
            ELSE IF EXISTS (SELECT 1 FROM inserted)
                SET @op = 'INSERT';
            ELSE
                SET @op = 'DELETE';

            INSERT INTO data_change_log (table_name, operation, record_id, old_data, new_data)
            SELECT
                '{table}',
                @op,
                CAST(COALESCE(i.[{pk_col}], d.[{pk_col}]) AS NVARCHAR(255)),
                (SELECT d.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER),
                (SELECT i.* FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
            FROM inserted i
            FULL OUTER JOIN deleted d ON i.[{pk_col}] = d.[{pk_col}];
        END
        """
        with self.engine.begin() as conn:
            conn.execute(text(body))
        logger.info("SQL Server CDC trigger installed for %s", table)

    def get_changes(
        self,
        since_change_id: Optional[int] = None,
        table_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[ChangeEvent]:
        # SQL Server uses TOP; OFFSET is also valid but TOP is friendlier here.
        sql = (f"SELECT TOP {int(limit)} change_id, table_name, operation, "
               "record_id, old_data, new_data, changed_at "
               "FROM data_change_log WHERE 1=1")
        params: Dict[str, Any] = {}
        if since_change_id is not None:
            sql += " AND change_id > :sid"; params["sid"] = since_change_id
        if table_name:
            sql += " AND table_name = :tname"; params["tname"] = table_name
        sql += " ORDER BY change_id"

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
                        database_type="sqlserver",
                    ))
        except Exception as exc:
            logger.error("SQL Server get_changes failed: %s", exc)
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
                    "SELECT COUNT(*) FROM sys.triggers t "
                    "JOIN sys.tables tb ON t.parent_id = tb.object_id "
                    "WHERE tb.name = :t AND t.name = :n"
                ), {"t": table_name, "n": f"trg_{table_name}_cdc"}).scalar()
            return bool(cnt)
        except Exception:
            return False

    # ── helpers ──────────────────────────────────────────────────────────────
    def _assert_table_exists(self, table_name: str) -> None:
        valid = sa_inspect(self.engine).get_table_names()
        if table_name not in valid:
            raise ValueError(f"Unknown SQL Server table: {table_name!r}. "
                             f"Available: {sorted(valid)}")


def _load_json(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {"_raw": str(value)}
