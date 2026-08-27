"""
Oracle Adapter — oracledb / cx_Oracle ETL + trigger-based CDC.

Connection-string forms accepted by ``CDCAdapterFactory``:
    oracle://user:pass@host:port/service_name
    oracle+oracledb://...
    oracle+cx_oracle://...

Driver
------
We prefer the modern ``oracledb`` package (thin mode — no Oracle Instant
Client required).  ``cx_Oracle`` is supported as fallback when only the
legacy driver is installed.

CDC strategy
------------
Oracle's premium CDC features (LogMiner, Streams, GoldenGate) require
licences and admin-level configuration that are out of scope for the
project's free Oracle XE Docker image (``gvenzl/oracle-xe:21-slim``).
We instead use the trigger + change-log pattern that mirrors the other
adapters: a ``DATA_CHANGE_LOG`` table populated by row-level triggers,
polled via ``change_id > :since``.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import create_engine, text, inspect as sa_inspect
from sqlalchemy.engine import Engine

from cdc.base_adapter import CDCAdapter, ChangeEvent, OperationType

logger = logging.getLogger(__name__)


def _detect_oracle_driver() -> Optional[str]:
    try:
        import oracledb  # noqa: F401
        return "oracledb"
    except ImportError:
        pass
    try:
        import cx_Oracle  # noqa: F401
        return "cx_oracle"
    except ImportError:
        return None


def _to_sqlalchemy_url(connection_string: str) -> str:
    """
    Promote ``oracle://...`` to the chosen driver and switch from SID
    semantics (``/XE``) to service-name semantics (``/?service_name=XE``)
    when the database segment looks like a pluggable database name
    (e.g. XEPDB1) — Oracle XE 21c registers PDBs as services, not SIDs.
    """
    if connection_string.startswith(("oracle+oracledb://", "oracle+cx_oracle://")):
        return connection_string

    drv = _detect_oracle_driver()
    if drv is None:
        raise ImportError(
            "Oracle adapter requires the 'oracledb' (preferred) or "
            "'cx_Oracle' Python package. Install with: pip install oracledb"
        )
    if connection_string.startswith("oracle://"):
        body = connection_string[len("oracle://"):]
    else:
        return connection_string

    # If the DB segment starts with a known PDB pattern OR is XEPDB1, swap
    # to ?service_name= form so SQLAlchemy + oracledb dial via SERVICE_NAME.
    m = re.match(r"^(.+@[^/]+)/([^?]+)(\?.*)?$", body)
    if m:
        prefix, dbseg, query = m.group(1), m.group(2), m.group(3) or ""
        if dbseg.upper() in {"XEPDB1", "FREEPDB1", "ORCLPDB1"} or "PDB" in dbseg.upper():
            sep = "&" if query.startswith("?") else "?"
            body = f"{prefix}/{sep}service_name={dbseg}".replace("?&", "?")
            # Above produces "...host/?service_name=XEPDB1" — clean trailing slashes
            body = re.sub(r"/(\?)", r"\1", body)
    return f"oracle+{drv}://{body}"


class OracleAdapter(CDCAdapter):
    """Oracle XE / Enterprise trigger-based CDC + ETL adapter."""

    SUPPORTS_NATIVE_CDC = True
    SUPPORTS_TRANSACTIONS = True

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self.sqlalchemy_url = _to_sqlalchemy_url(connection_string)
        self._engine: Optional[Engine] = None

    # ── identity ─────────────────────────────────────────────────────────────
    def get_database_type(self) -> str:
        return "oracle"

    # ── connection lifecycle ─────────────────────────────────────────────────
    def connect(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(
                self.sqlalchemy_url,
                pool_pre_ping=True,
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
                conn.execute(text("SELECT 1 FROM DUAL"))
            return True
        except Exception as exc:
            logger.warning("Oracle connection validation failed: %s", exc)
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
                        text(f'SELECT COUNT(*) FROM "{tname.upper()}"')
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
            "database_type": "oracle",
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
        # Oracle 12c+ supports ``OFFSET .. ROWS FETCH NEXT`` natively.
        sql = f'SELECT * FROM "{table_name.upper()}"'
        params: Dict[str, Any] = {}
        if limit is not None:
            sql += " OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY"
            params = {"off": int(offset), "lim": int(limit)}
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [{k.lower(): v for k, v in dict(r).items()} for r in rows]

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
        col_csv = ", ".join(f'"{c.upper()}"' for c in cols)
        bind_csv = ", ".join(f":{c}" for c in cols)

        if upsert_keys:
            on_clause = " AND ".join(
                f'T."{k.upper()}" = S."{k.upper()}"' for k in upsert_keys
            )
            non_key = [c for c in cols if c not in upsert_keys]
            update = ", ".join(
                f'T."{c.upper()}" = S."{c.upper()}"' for c in non_key
            ) or f'T."{cols[0].upper()}" = S."{cols[0].upper()}"'
            ins_cols = ", ".join(f'"{c.upper()}"' for c in cols)
            ins_vals = ", ".join(f'S."{c.upper()}"' for c in cols)
            select_cols = ", ".join(f':{c} AS "{c.upper()}"' for c in cols)
            sql = (f'MERGE INTO "{table_name.upper()}" T '
                   f'USING (SELECT {select_cols} FROM DUAL) S '
                   f'ON ({on_clause}) '
                   f'WHEN MATCHED THEN UPDATE SET {update} '
                   f'WHEN NOT MATCHED THEN INSERT ({ins_cols}) VALUES ({ins_vals})')
        else:
            sql = (f'INSERT INTO "{table_name.upper()}" ({col_csv}) '
                   f'VALUES ({bind_csv})')

        written = 0
        with self.engine.begin() as conn:
            for r in rows:
                conn.execute(text(sql), r)
                written += 1
        return written

    # ── CDC setup ────────────────────────────────────────────────────────────
    def setup_cdc(self, tables: List[str]) -> bool:
        try:
            self._ensure_change_log()
            self._ensure_sequence()
            inspector = sa_inspect(self.engine)
            valid = {t.upper() for t in inspector.get_table_names()}
            for table in tables:
                if table.upper() not in valid:
                    logger.warning("Oracle CDC: skipping unknown table %s", table)
                    continue
                self._install_triggers(table.upper(), inspector)
            self.is_setup = True
            return True
        except Exception as exc:
            logger.error("Oracle CDC setup failed: %s", exc, exc_info=True)
            return False

    def _ensure_change_log(self) -> None:
        ddl = """
        BEGIN
            EXECUTE IMMEDIATE '
                CREATE TABLE DATA_CHANGE_LOG (
                    CHANGE_ID   NUMBER PRIMARY KEY,
                    TABLE_NAME  VARCHAR2(100) NOT NULL,
                    OPERATION   VARCHAR2(10)  NOT NULL,
                    RECORD_ID   VARCHAR2(255),
                    OLD_DATA    CLOB,
                    NEW_DATA    CLOB,
                    CHANGED_AT  TIMESTAMP DEFAULT SYSTIMESTAMP,
                    USER_NAME   VARCHAR2(100) DEFAULT USER,
                    TENANT_ID   NUMBER
                )';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE != -955 THEN RAISE; END IF;  -- 955 = name in use
        END;
        """
        with self.engine.begin() as conn:
            conn.execute(text(ddl))

    def _ensure_sequence(self) -> None:
        ddl = """
        BEGIN
            EXECUTE IMMEDIATE 'CREATE SEQUENCE DATA_CHANGE_LOG_SEQ START WITH 1 INCREMENT BY 1 NOCACHE';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
        with self.engine.begin() as conn:
            conn.execute(text(ddl))

    def _install_triggers(self, table: str, inspector) -> None:
        pks = inspector.get_pk_constraint(table.lower()).get("constrained_columns", []) \
              or inspector.get_pk_constraint(table).get("constrained_columns", [])
        pk_col = pks[0].upper() if pks else "ID"
        col_names = [c["name"].upper() for c in inspector.get_columns(table.lower())]

        def _json(prefix: str) -> str:
            # Oracle 12.2+ has JSON_OBJECT
            parts = ", ".join(f"'{c}' VALUE :{prefix.lower()}_{c}".replace(":", "")
                              for c in col_names)
            # Build via Oracle SQL directly using the trigger's :NEW/:OLD aliases
            inner = ", ".join(f"'{c}' VALUE :{prefix}.\"{c}\"" for c in col_names)
            return f"JSON_OBJECT({inner})" if inner else "TO_CLOB('{}')"

        new_obj = _json("NEW")
        old_obj = _json("OLD")
        trig = f"TRG_{table}_CDC"

        body = f"""
        CREATE OR REPLACE TRIGGER {trig}
        AFTER INSERT OR UPDATE OR DELETE ON "{table}"
        FOR EACH ROW
        DECLARE
            v_op   VARCHAR2(10);
            v_rid  VARCHAR2(255);
            v_old  CLOB := NULL;
            v_new  CLOB := NULL;
        BEGIN
            IF INSERTING THEN
                v_op  := 'INSERT';
                v_rid := TO_CHAR(:NEW."{pk_col}");
                v_new := {new_obj};
            ELSIF UPDATING THEN
                v_op  := 'UPDATE';
                v_rid := TO_CHAR(:NEW."{pk_col}");
                v_old := {old_obj};
                v_new := {new_obj};
            ELSIF DELETING THEN
                v_op  := 'DELETE';
                v_rid := TO_CHAR(:OLD."{pk_col}");
                v_old := {old_obj};
            END IF;

            INSERT INTO DATA_CHANGE_LOG
                (CHANGE_ID, TABLE_NAME, OPERATION, RECORD_ID, OLD_DATA, NEW_DATA)
            VALUES
                (DATA_CHANGE_LOG_SEQ.NEXTVAL, '{table}', v_op, v_rid, v_old, v_new);
        END;
        """
        with self.engine.begin() as conn:
            conn.execute(text(body))
        logger.info("Oracle CDC trigger installed for %s", table)

    def get_changes(
        self,
        since_change_id: Optional[int] = None,
        table_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[ChangeEvent]:
        sql = ("SELECT CHANGE_ID, TABLE_NAME, OPERATION, RECORD_ID, "
               "OLD_DATA, NEW_DATA, CHANGED_AT "
               "FROM DATA_CHANGE_LOG WHERE 1=1")
        params: Dict[str, Any] = {}
        if since_change_id is not None:
            sql += " AND CHANGE_ID > :sid"; params["sid"] = since_change_id
        if table_name:
            sql += " AND TABLE_NAME = :tname"; params["tname"] = table_name
        sql += (" ORDER BY CHANGE_ID FETCH NEXT :lim ROWS ONLY")
        params["lim"] = int(limit)

        events: List[ChangeEvent] = []
        try:
            with self.engine.connect() as conn:
                for row in conn.execute(text(sql), params):
                    events.append(ChangeEvent(
                        change_id=int(row[0]),
                        table_name=row[1],
                        operation=OperationType[row[2]],
                        record_id=row[3],
                        old_data=_load_json(row[4]),
                        new_data=_load_json(row[5]),
                        changed_at=row[6],
                        database_type="oracle",
                    ))
        except Exception as exc:
            logger.error("Oracle get_changes failed: %s", exc)
        return events

    def get_latest_change_id(self) -> Optional[int]:
        try:
            with self.engine.connect() as conn:
                v = conn.execute(
                    text("SELECT MAX(CHANGE_ID) FROM DATA_CHANGE_LOG")
                ).scalar()
                return int(v) if v is not None else None
        except Exception:
            return None

    def is_cdc_enabled(self, table_name: str) -> bool:
        try:
            with self.engine.connect() as conn:
                cnt = conn.execute(text(
                    "SELECT COUNT(*) FROM USER_TRIGGERS "
                    "WHERE TABLE_NAME = :t AND TRIGGER_NAME = :n"
                ), {"t": table_name.upper(),
                    "n": f"TRG_{table_name.upper()}_CDC"}).scalar()
            return bool(cnt)
        except Exception:
            return False

    # ── helpers ──────────────────────────────────────────────────────────────
    def _assert_table_exists(self, table_name: str) -> None:
        valid = {t.upper() for t in sa_inspect(self.engine).get_table_names()}
        if table_name.upper() not in valid:
            raise ValueError(f"Unknown Oracle table: {table_name!r}. "
                             f"Available: {sorted(valid)}")


def _load_json(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if hasattr(value, "read"):  # CLOB / LOB
        try:
            value = value.read()
        except Exception:
            return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {"_raw": str(value)}
