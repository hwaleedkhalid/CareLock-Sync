"""
System Event Log — persistent SQLite-backed audit trail.

Logs auth, sync, and system events. Replaces the PHI-only audit logger
for general system observability.

Database: <backend_dir>/data/carelock_events.db
Table:    system_events
"""
import sqlite3, json, logging, os, threading
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Absolute path — same location regardless of cwd
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_DB_PATH  = os.path.join(_DATA_DIR, "carelock_events.db")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS system_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,
    user_email  TEXT,
    tenant_id   INTEGER,
    message     TEXT    NOT NULL,
    details     TEXT,           -- JSON blob
    ip_address  TEXT
)
"""
_CREATE_IDX_TS   = "CREATE INDEX IF NOT EXISTS idx_events_ts   ON system_events(timestamp)"
_CREATE_IDX_TYPE = "CREATE INDEX IF NOT EXISTS idx_events_type ON system_events(event_type)"


class SystemEventLog:
    """Thread-safe SQLite event logger."""

    def __init__(self, db_path: str = _DB_PATH) -> None:
        self.db_path = db_path
        self._lock   = threading.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(_CREATE_TABLE)
                conn.execute(_CREATE_IDX_TS)
                conn.execute(_CREATE_IDX_TYPE)
                conn.commit()
        logger.info(f"Event log ready: {self.db_path}")

    def write(
        self,
        event_type: str,
        user_email: Optional[str],
        tenant_id: Optional[int],
        message: str,
        details: Optional[Any] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Append one event row. Never raises — failures are logged only."""
        try:
            details_json = json.dumps(details) if details is not None else None
            with self._lock:
                with self._connect() as conn:
                    conn.execute(
                        """INSERT INTO system_events
                           (timestamp, event_type, user_email, tenant_id, message, details, ip_address)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (datetime.utcnow().isoformat(), event_type, user_email,
                         tenant_id, message, details_json, ip_address),
                    )
                    conn.commit()
        except Exception as exc:
            logger.error(f"Event log write failed: {exc}")

    def recent(self, limit: int = 100, event_type: Optional[str] = None) -> list[dict]:
        """Return the most recent events, newest first."""
        try:
            with self._connect() as conn:
                if event_type:
                    rows = conn.execute(
                        "SELECT * FROM system_events WHERE event_type=? ORDER BY id DESC LIMIT ?",
                        (event_type, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM system_events ORDER BY id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error(f"Event log read failed: {exc}")
            return []

    def stats(self) -> dict:
        """Return aggregate counts by event_type."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT event_type, COUNT(*) as count FROM system_events GROUP BY event_type"
                ).fetchall()
            return {r["event_type"]: r["count"] for r in rows}
        except Exception as exc:
            logger.error(f"Event log stats failed: {exc}")
            return {}


# Singleton — import and use directly
event_log = SystemEventLog()
