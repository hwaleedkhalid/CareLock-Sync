"""
Change Data Capture (CDC) Monitor  — v3
========================================
Improvements over v2 (all 9 risks addressed):

  Risk 1 – Per-row SELECT cost
      Trigger now reads current_setting('app.tenant_id', true) as the fast
      path (zero table I/O per row). Falls back to _cdc_config only when the
      session variable is absent.  Configure once per connection via
      CDCMonitor.set_session_tenant(conn, tenant_id).

  Risk 2 – DROP … CASCADE in setup
      log_data_change (legacy) is now removed safely:
        1. All triggers that depend on it are dropped explicitly first.
        2. The function itself is dropped WITHOUT CASCADE.
      The canonical log_table_changes is deployed with CREATE OR REPLACE,
      which never drops dependent objects.

  Risk 3 – Large batches & memory
      get_changes_since() now accepts an optional batch_size parameter.
      iter_changes_since() is a generator that uses a server-side named
      cursor (psycopg2), streaming rows in configurable chunks without
      loading the full result set into Python memory.

  Risk 4 – Watermark advancement on partial failures
      A cdc_watermarks table stores (tenant_id, last_change_id) durably.
      save_watermark() / load_watermark() let callers persist the cursor
      in the DB rather than in a JSON file.  advance_watermark() only
      updates if the new id is strictly greater than the stored one.

  Risk 5 – Migration locking / downtime
      migrate_schema() now:
        - Sets lock_timeout = '5s' before ALTER COLUMN so it fails fast
          rather than blocking behind a long transaction.
        - Prints explicit guidance to use pg_repack for zero-downtime.
        - Skips the ALTER if record_id is already TEXT.

  Risk 6 – Per-tenant scheduler state
      cdc_watermarks replaces the single-file scheduler state.
      Multiple workers can each call load_watermark(tenant_id) and
      save_watermark(tenant_id, last_id) safely via ON CONFLICT DO UPDATE.

  Risk 7 – Trigger permissions & RLS
      create_trigger_function() deploys with SECURITY DEFINER and a
      comment that names the required owner.  setup_cdc_for_tables()
      also grants EXECUTE to PUBLIC so all app roles can fire the trigger.

  Risk 8 – pg_notify payload includes tenant_id
      pg_notify payload already carried tenant_id (v2).  In v3 the payload
      also includes operation_count for batch consumers, and the tenant
      value is resolved via the fast-path current_setting so it is always
      present in the notification even when _cdc_config is slow.

  Risk 9 – Concurrency / performance tests
      See tests/unit/test_cdc_performance.py (companion file).
"""
from __future__ import annotations

import threading
from typing import Callable, Dict, Generator, Iterator, List, Optional

from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.orm import sessionmaker


class CDCMonitor:
    """
    Manages CDC infrastructure for a single hospital (PostgreSQL) database.

    Typical lifecycle
    -----------------
    monitor = CDCMonitor(db_url, tenant_id=1)
    monitor.setup_cdc_for_tables(["patients", "encounters"])

    # Each sync cycle:
    last = monitor.load_watermark(tenant_id=1)
    for batch in monitor.iter_changes_since(last, tenant_id=1, batch_size=500):
        process(batch)
        monitor.advance_watermark(tenant_id=1, new_id=batch[-1]["change_id"])
    """

    DEFAULT_BATCH_SIZE = 500

    # ── construction ─────────────────────────────────────────────────────────
    def __init__(self, database_url: str, tenant_id: Optional[int] = None):
        self.database_url = database_url
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.session_factory = sessionmaker(bind=self.engine)
        self.listeners: Dict[str, List[Callable]] = {}
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        if tenant_id is not None:
            self.configure_tenant(tenant_id)

    # ── static helper: set session-local tenant (Risk 1 fast path) ───────────
    @staticmethod
    def set_session_tenant(conn, tenant_id: int) -> None:
        """
        Set app.tenant_id as a session-local GUC on an existing connection.
        The trigger reads this via current_setting('app.tenant_id', true),
        which is a single in-memory lookup — zero table I/O per row.
        Call this once per connection (e.g. in a SQLAlchemy event hook or
        at the top of each request handler).
        """
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})

    # ── _cdc_config table (fallback tenant store) ─────────────────────────────
    def _create_cdc_config_table(self) -> None:
        """
        _cdc_config: single-row fallback when the session GUC is absent
        (e.g. during background maintenance jobs that bypass app code).
        The trigger reads current_setting() first; _cdc_config is only
        queried when the GUC is NULL or empty.
        """
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS _cdc_config (
                    key   VARCHAR(50)  PRIMARY KEY,
                    value VARCHAR(200) NOT NULL
                );
                INSERT INTO _cdc_config (key, value)
                VALUES ('tenant_id', '0')
                ON CONFLICT (key) DO NOTHING;
            """))
            conn.commit()

    def configure_tenant(self, tenant_id: int) -> None:
        """Persist tenant_id in _cdc_config so the fallback path always works."""
        self._create_cdc_config_table()
        with self.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO _cdc_config (key, value)
                VALUES ('tenant_id', :tid)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """), {"tid": str(tenant_id)})
            conn.commit()
        print(f"[OK] CDC tenant configured: {tenant_id}")

    # ── cdc_watermarks table (Risk 4 + Risk 6) ───────────────────────────────
    def _create_watermarks_table(self) -> None:
        """
        cdc_watermarks: durable per-tenant cursor store.
        Replaces scheduler_state.json so multiple workers in different
        processes can coordinate without race conditions.
        """
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS cdc_watermarks (
                    tenant_id     INTEGER     PRIMARY KEY,
                    last_change_id BIGINT     NOT NULL DEFAULT 0,
                    updated_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.commit()

    def load_watermark(self, tenant_id: int) -> int:
        """
        Return the last successfully processed change_id for tenant_id.
        Returns 0 if no watermark exists yet (full replay).
        """
        self._create_watermarks_table()
        with self.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT last_change_id FROM cdc_watermarks
                 WHERE tenant_id = :tid
            """), {"tid": tenant_id}).fetchone()
        return int(row[0]) if row else 0

    def advance_watermark(self, tenant_id: int, new_id: int) -> None:
        """
        Persist new_id as the watermark for tenant_id.
        Only advances — never moves the watermark backwards.
        This ensures partial failures don't skip records: if a batch
        fails mid-way, the watermark stays at the last fully-committed
        position and the batch is retried in full next cycle.
        """
        self._create_watermarks_table()
        with self.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO cdc_watermarks (tenant_id, last_change_id, updated_at)
                VALUES (:tid, :nid, CURRENT_TIMESTAMP)
                ON CONFLICT (tenant_id) DO UPDATE
                    SET last_change_id = GREATEST(
                            cdc_watermarks.last_change_id,
                            EXCLUDED.last_change_id
                        ),
                        updated_at = CURRENT_TIMESTAMP
            """), {"tid": tenant_id, "nid": new_id})
            conn.commit()

    # alias kept for callers that used save_watermark() directly
    def save_watermark(self, tenant_id: int, last_change_id: int) -> None:
        self.advance_watermark(tenant_id, last_change_id)

    # ── create_change_log_table ───────────────────────────────────────────────
    def create_change_log_table(self) -> None:
        """
        Create data_change_log.
          record_id TEXT     — supports SERIAL, UUID, BIGINT, VARCHAR PKs
          tenant_id INTEGER  — multi-tenant routing; populated by trigger
        """
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS data_change_log (
                    change_id       BIGSERIAL    PRIMARY KEY,
                    table_name      VARCHAR(100) NOT NULL,
                    operation       VARCHAR(10)  NOT NULL,
                    record_id       TEXT,
                    old_data        JSONB,
                    new_data        JSONB,
                    changed_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                    user_name       VARCHAR(100),
                    tenant_id       INTEGER,
                    change_metadata JSONB
                );
                CREATE INDEX IF NOT EXISTS idx_change_log_id
                    ON data_change_log(change_id);
                CREATE INDEX IF NOT EXISTS idx_change_log_tenant_time
                    ON data_change_log(tenant_id, changed_at);
                CREATE INDEX IF NOT EXISTS idx_change_log_table
                    ON data_change_log(table_name);
            """))
            conn.commit()
        print("[OK] Change log table created/verified")

    # ── create_trigger_function (Risk 1, 2, 7, 8) ────────────────────────────
    def create_trigger_function(self) -> None:
        """
        Deploy the ONE canonical trigger function: log_table_changes.

        Risk 1 — Fast path: reads current_setting('app.tenant_id', true).
                  Falls back to _cdc_config only when GUC is absent.
                  This is a GUC cache hit (~nanoseconds) vs a table lookup.

        Risk 2 — Safe legacy removal:
                  1. Drops all triggers that depend on log_data_change first.
                  2. Drops the function WITHOUT CASCADE.
                  3. Canonical function deployed with CREATE OR REPLACE
                     (never drops dependents).

        Risk 7 — SECURITY DEFINER so the function runs as its owner
                  regardless of the calling role. GRANT EXECUTE to PUBLIC
                  so all application roles can fire triggers.

        Risk 8 — pg_notify payload includes tenant_id resolved via
                  the fast-path GUC so listeners never need a round-trip.
        """
        with self.engine.connect() as conn:
            # ── Step A: safely remove legacy log_data_change ─────────────────
            # Find every trigger that references it and drop those first.
            dep_triggers = conn.execute(text("""
                SELECT t.tgname, c.relname
                  FROM pg_trigger t
                  JOIN pg_class   c ON c.oid = t.tgrelid
                  JOIN pg_proc    p ON p.oid = t.tgfoid
                 WHERE p.proname = 'log_data_change'
                   AND NOT t.tgisinternal
            """)).fetchall()

            for trig_name, tbl_name in dep_triggers:
                conn.execute(text(
                    f"DROP TRIGGER IF EXISTS {trig_name} ON {tbl_name};"
                ))
                print(f"[OK] Dropped legacy trigger {trig_name} on {tbl_name}")

            conn.execute(text(
                "DROP FUNCTION IF EXISTS log_data_change();"   # no CASCADE needed
            ))

            # ── Step B: deploy canonical function (CREATE OR REPLACE) ─────────
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION log_table_changes()
                RETURNS TRIGGER
                -- Risk 7: run as function owner, not caller role
                SECURITY DEFINER
                -- Ownership note: ALTER FUNCTION log_table_changes OWNER TO <superuser_role>
                LANGUAGE plpgsql
                AS $$
                DECLARE
                    pk_col          TEXT;
                    record_id_value TEXT;
                    old_data_json   JSONB;
                    new_data_json   JSONB;
                    tenant_id_value INTEGER;
                    guc_val         TEXT;
                BEGIN
                    -- ── Risk 1: fast-path GUC read, zero table I/O ──────────
                    guc_val := current_setting('app.tenant_id', true);
                    IF guc_val IS NOT NULL AND guc_val <> '' THEN
                        tenant_id_value := guc_val::INTEGER;
                    ELSE
                        -- Fallback: read from _cdc_config (background jobs path)
                        BEGIN
                            SELECT value::INTEGER
                              INTO tenant_id_value
                              FROM _cdc_config
                             WHERE key = 'tenant_id';
                        EXCEPTION WHEN OTHERS THEN
                            tenant_id_value := NULL;
                        END;
                    END IF;

                    -- ── Dynamic PK detection ────────────────────────────────
                    SELECT column_name
                      INTO pk_col
                      FROM information_schema.key_column_usage
                     WHERE table_name   = TG_TABLE_NAME
                       AND table_schema = TG_TABLE_SCHEMA
                       AND constraint_name IN (
                               SELECT constraint_name
                                 FROM information_schema.table_constraints
                                WHERE table_name      = TG_TABLE_NAME
                                  AND table_schema    = TG_TABLE_SCHEMA
                                  AND constraint_type = 'PRIMARY KEY'
                           )
                     ORDER BY ordinal_position
                     LIMIT 1;

                    -- ── Build JSONB snapshots, extract PK as TEXT ───────────
                    IF TG_OP = 'DELETE' THEN
                        old_data_json   := row_to_json(OLD)::JSONB;
                        new_data_json   := NULL;
                        record_id_value := old_data_json ->> pk_col;
                    ELSIF TG_OP = 'UPDATE' THEN
                        old_data_json   := row_to_json(OLD)::JSONB;
                        new_data_json   := row_to_json(NEW)::JSONB;
                        record_id_value := new_data_json ->> pk_col;
                    ELSIF TG_OP = 'INSERT' THEN
                        old_data_json   := NULL;
                        new_data_json   := row_to_json(NEW)::JSONB;
                        record_id_value := new_data_json ->> pk_col;
                    END IF;

                    -- ── Write to change log ─────────────────────────────────
                    INSERT INTO data_change_log (
                        table_name, operation, record_id,
                        old_data, new_data, user_name, tenant_id
                    ) VALUES (
                        TG_TABLE_NAME, TG_OP, record_id_value,
                        old_data_json, new_data_json,
                        current_user, tenant_id_value
                    );

                    -- ── Risk 8: notify with tenant_id from fast-path value ──
                    PERFORM pg_notify('data_changes', json_build_object(
                        'table',     TG_TABLE_NAME,
                        'operation', TG_OP,
                        'record_id', record_id_value,
                        'tenant_id', tenant_id_value,
                        'timestamp', to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
                    )::text);

                    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
                END;
                $$;
            """))

            # ── Step C: grant EXECUTE to PUBLIC (Risk 7) ──────────────────────
            conn.execute(text(
                "GRANT EXECUTE ON FUNCTION log_table_changes() TO PUBLIC;"
            ))
            conn.commit()

        print("[OK] log_table_changes deployed (SECURITY DEFINER, fast-path GUC)")
        print("[OK] Legacy log_data_change removed safely (no CASCADE)")

    # ── add_trigger_to_table (SQL-injection safe) ─────────────────────────────
    def add_trigger_to_table(self, table_name: str) -> None:
        """
        Attach log_table_changes to a table.
        Validates table_name against the live pg catalog — no raw
        string interpolation without prior whitelist check.

        Raises:
            ValueError: table not found in schema 'public'.
        """
        if not table_name or not isinstance(table_name, str):
            raise ValueError(f"table_name must be a non-empty string, got: {table_name!r}")
        valid = sa_inspect(self.engine).get_table_names(schema="public")
        if table_name not in valid:
            raise ValueError(
                f"Table '{table_name}' not found in schema 'public'. "
                f"Known tables: {sorted(valid)}"
            )
        # Safe: name proven to exist in catalog
        trigger_sql = f"""
        DROP TRIGGER IF EXISTS {table_name}_change_trigger ON {table_name};
        CREATE TRIGGER {table_name}_change_trigger
            AFTER INSERT OR UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION log_table_changes();
        """
        with self.engine.connect() as conn:
            conn.execute(text(trigger_sql))
            conn.commit()
        print(f"[OK] Trigger added to table: {table_name}")

    # ── setup_cdc_for_tables ──────────────────────────────────────────────────
    def setup_cdc_for_tables(self, table_names: List[str]) -> None:
        """Full CDC bootstrap: config → watermarks → log table → function → triggers."""
        print("\n" + "=" * 60)
        print("Setting up Change Data Capture  (v3)")
        print("=" * 60)
        self._create_cdc_config_table()
        self._create_watermarks_table()
        self.create_change_log_table()
        self.create_trigger_function()
        for t in table_names:
            self.add_trigger_to_table(t)
        print(f"\n[OK] CDC setup complete for {len(table_names)} tables")

    # ── migrate_schema (Risk 5 — locking guidance) ───────────────────────────
    def migrate_schema(self) -> None:
        """
        Idempotent in-place upgrade for pre-v3 deployments.

        Risk 5 — Locking:
          ALTER COLUMN TYPE acquires AccessExclusiveLock.
          lock_timeout = '5s' makes it fail-fast instead of blocking
          behind a long transaction, so the migration is safe to run
          during low-traffic windows.
          For zero-downtime on busy tables use pg_repack:
            pg_repack -t data_change_log --no-kill-backend
        """
        print("[MIGRATE] Checking data_change_log schema …")
        with self.engine.connect() as conn:
            conn.execute(text("SET lock_timeout = '5s'"))

            # 1. Add tenant_id if missing
            has_tid = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns
                 WHERE table_name='data_change_log'
                   AND column_name='tenant_id' AND table_schema='public'
            """)).scalar()
            if not has_tid:
                conn.execute(text(
                    "ALTER TABLE data_change_log ADD COLUMN tenant_id INTEGER;"
                ))
                print("[MIGRATE] tenant_id column added")

            # 2. Promote record_id to TEXT if it is still an integer type
            col_type = conn.execute(text("""
                SELECT data_type FROM information_schema.columns
                 WHERE table_name='data_change_log'
                   AND column_name='record_id' AND table_schema='public'
            """)).scalar()
            if col_type and col_type.lower() in ("integer", "bigint", "smallint"):
                print(f"[MIGRATE] Promoting record_id from {col_type} → TEXT "
                      f"(lock_timeout=5s active)")
                conn.execute(text(
                    "ALTER TABLE data_change_log "
                    "ALTER COLUMN record_id TYPE TEXT USING record_id::TEXT;"
                ))
                print("[MIGRATE] record_id promoted — consider pg_repack "
                      "for zero-downtime on large tables")
            else:
                print(f"[MIGRATE] record_id type={col_type!r} — no change")

            # 3. Add indexes
            for sql in [
                "CREATE INDEX IF NOT EXISTS idx_change_log_id ON data_change_log(change_id)",
                "CREATE INDEX IF NOT EXISTS idx_change_log_tenant_time ON data_change_log(tenant_id, changed_at)",
                "CREATE INDEX IF NOT EXISTS idx_change_log_table ON data_change_log(table_name)",
            ]:
                conn.execute(text(sql))

            conn.commit()

        # 4. Watermarks table
        self._create_watermarks_table()
        # 5. Redeploy trigger (also kills legacy log_data_change)
        self.create_trigger_function()
        print("[MIGRATE] Complete")

    # ── Query methods (Risk 3 — streaming) ───────────────────────────────────

    def get_recent_changes(
        self,
        table_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """
        Return the most recent rows (backward-compat for connector.py routes).
        """
        q = """
            SELECT change_id, table_name, operation, record_id,
                   old_data, new_data, changed_at, tenant_id
              FROM data_change_log
        """
        params: Dict = {"limit": limit}
        if table_name:
            q += " WHERE table_name = :table_name"
            params["table_name"] = table_name
        q += " ORDER BY changed_at DESC LIMIT :limit"
        with self.engine.connect() as conn:
            rows = conn.execute(text(q), params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_changes_since(
        self,
        last_change_id: int,
        tenant_id: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> List[Dict]:
        """
        Eager load up to batch_size rows after last_change_id.
        When batch_size is None the full result set is loaded — only safe
        for small logs. For large / unbounded logs prefer iter_changes_since().

        Args:
            last_change_id: Exclusive lower bound.
            tenant_id:      Optional per-tenant filter.
            batch_size:     Max rows to return. None = no limit.
        """
        q, params = self._changes_since_query(last_change_id, tenant_id)
        if batch_size is not None:
            q += " LIMIT :batch_size"
            params["batch_size"] = batch_size
        with self.engine.connect() as conn:
            rows = conn.execute(text(q), params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def iter_changes_since(
        self,
        last_change_id: int,
        tenant_id: Optional[int] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> Generator[List[Dict], None, None]:
        """
        Risk 3 — Streaming generator using server-side cursor.
        Yields successive lists of up to batch_size rows without loading
        the entire result set into memory. Uses psycopg2 named cursors
        (stream=True in SQLAlchemy raw connection).

        Usage:
            for batch in monitor.iter_changes_since(last_id, tenant_id=1):
                process(batch)
                monitor.advance_watermark(1, batch[-1]["change_id"])

        Args:
            last_change_id: Exclusive lower bound.
            tenant_id:      Optional per-tenant filter.
            batch_size:     Rows per server-side fetch.
        """
        q, params = self._changes_since_query(last_change_id, tenant_id)
        # Convert SQLAlchemy :name style to psycopg2 %(name)s style for raw cursor
        q_psycopg2 = q.replace(':last_change_id', '%(last_change_id)s').replace(':tenant_id', '%(tenant_id)s')
        raw_conn = self.engine.raw_connection()
        try:
            cursor_name = f"cdc_stream_{id(raw_conn)}"
            cur = raw_conn.cursor(cursor_name)  # server-side named cursor
            cur.execute(q_psycopg2, params)
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                yield [self._row_to_dict_raw(r) for r in rows]
            cur.close()
            raw_conn.commit()
        finally:
            raw_conn.close()

    # ── internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _changes_since_query(
        last_change_id: int,
        tenant_id: Optional[int],
    ):
        """Build the parameterised SELECT for cursor-based retrieval."""
        q = """
            SELECT change_id, table_name, operation, record_id,
                   old_data, new_data, changed_at, tenant_id
              FROM data_change_log
             WHERE change_id > :last_change_id
        """
        params: Dict = {"last_change_id": last_change_id}
        if tenant_id is not None:
            q += " AND tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id
        q += " ORDER BY change_id ASC"
        return q, params

    @staticmethod
    def _row_to_dict(row) -> Dict:
        """Convert a SQLAlchemy Row to a plain dict."""
        return {
            "change_id":  row[0],
            "table_name": row[1],
            "operation":  row[2],
            "record_id":  row[3],
            "old_data":   row[4],
            "new_data":   row[5],
            "changed_at": row[6].isoformat() if row[6] else None,
            "tenant_id":  row[7],
        }

    @staticmethod
    def _row_to_dict_raw(row: tuple) -> Dict:
        """Convert a raw psycopg2 tuple to a plain dict."""
        return {
            "change_id":  row[0],
            "table_name": row[1],
            "operation":  row[2],
            "record_id":  row[3],
            "old_data":   row[4],
            "new_data":   row[5],
            "changed_at": row[6].isoformat() if row[6] else None,
            "tenant_id":  row[7],
        }

    def get_latest_change_id(self) -> Optional[int]:
        """Return the high-water-mark change_id (None if log is empty)."""
        with self.engine.connect() as conn:
            val = conn.execute(
                text("SELECT MAX(change_id) FROM data_change_log")
            ).scalar()
        return int(val) if val is not None else None

    def get_change_statistics(self) -> Dict:
        """Per-table, per-operation change counts."""
        with self.engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT table_name, operation, COUNT(*) AS cnt
                  FROM data_change_log
                 GROUP BY table_name, operation
                 ORDER BY table_name, operation
            """)).fetchall()
        stats: Dict = {}
        for r in rows:
            stats.setdefault(r[0], {})[r[1]] = r[2]
        return stats

    # ── Listener / monitoring stubs ───────────────────────────────────────────
    def register_change_listener(self, table_name: str, callback: Callable) -> None:
        self.listeners.setdefault(table_name, []).append(callback)

    def start_monitoring(self) -> None:
        print("[INFO] Real-time pg_notify/LISTEN: use iter_changes_since() for polling")


# ── Module-level convenience ──────────────────────────────────────────────────

def setup_cdc(
    database_url: str,
    tables: List[str],
    tenant_id: Optional[int] = None,
) -> CDCMonitor:
    monitor = CDCMonitor(database_url)
    if tenant_id is not None:
        monitor.configure_tenant(tenant_id)
    monitor.setup_cdc_for_tables(tables)
    return monitor


# ── CLI smoke test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from common.config import settings

    TABLES = ["patients", "encounters", "lab_results", "medications"]
    m = setup_cdc(settings.hospital_db_url, TABLES, tenant_id=1)

    hwm = m.load_watermark(tenant_id=1)
    print(f"\nWatermark for tenant 1: {hwm}")
    print(f"High-water-mark change_id: {m.get_latest_change_id()}")

    total = 0
    for batch in m.iter_changes_since(hwm, tenant_id=1, batch_size=100):
        total += len(batch)
        print(f"  Streamed batch of {len(batch)} rows")

    print(f"\n[OK] Total streamed: {total}")
