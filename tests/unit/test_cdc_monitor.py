"""
tests/unit/test_cdc_monitor.py
================================
Comprehensive pytest suite for CDCMonitor v2.

Covers every fix and requirement:
  Schema     — tenant_id column, record_id TEXT, no duplicate trigger functions
  Integer PK — INSERT / UPDATE / DELETE with a standard SERIAL id
  UUID PK    — INSERT / UPDATE / DELETE with a gen_random_uuid() PK
  Text PK    — INSERT / UPDATE / DELETE with a varchar PK
  Tenant     — tenant_id flows from _cdc_config into every change row
  Cursor     — get_changes_since() returns incremental results correctly
  Security   — add_trigger_to_table() raises ValueError on bad names

Prerequisites
--------------
  • PostgreSQL running (Docker or native)
  • Environment variable TEST_DB_URL  (falls back to the project's HOSPITAL_DB_URL)
  • pip install pytest psycopg2-binary python-dotenv

Run:
    pytest tests/unit/test_cdc_monitor.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
import pytest

from sqlalchemy import create_engine, text, inspect as sa_inspect

# ── path bootstrap so we can import without installing the package ────────────
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from connector.cdc_monitor import CDCMonitor, setup_cdc

# ── helpers ───────────────────────────────────────────────────────────────────

def _get_test_db_url() -> str:
    """
    Resolve test DB URL.
    Priority: TEST_DB_URL env var → project .env HOSPITAL_DB_URL → hard default.
    """
    explicit = os.environ.get("TEST_DB_URL")
    if explicit:
        return explicit
    # Try loading the project .env
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        from dotenv import dotenv_values
        vals = dotenv_values(env_path)
        if vals.get("HOSPITAL_DB_URL"):
            return vals["HOSPITAL_DB_URL"]
    return "postgresql://hospital_user:hospital_pass@localhost:5432/hospital_db"

# ── Session-scoped fixtures ───────────────────────────────────────────────────

TEST_TENANT_ID = 42   # arbitrary non-default value so we can assert it arrived

@pytest.fixture(scope="session")
def db_engine():
    """Create an engine for the test database."""
    url = _get_test_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def cdc(db_engine):
    """
    Bootstrap CDCMonitor once per test session:
      - configure tenant
      - create log table + trigger function
    Individual table creation / trigger attachment happens in per-test fixtures.
    """
    monitor = CDCMonitor(db_engine.url.render_as_string(hide_password=False))
    monitor.configure_tenant(TEST_TENANT_ID)
    monitor.create_change_log_table()
    monitor.create_trigger_function()
    yield monitor


# ── Per-test table fixtures ───────────────────────────────────────────────────

@pytest.fixture()
def int_pk_table(db_engine, cdc):
    """
    Temporary table with a SERIAL (integer) primary key.
    Trigger is attached; table is dropped after the test.
    """
    tbl = "cdc_test_int_pk"
    with db_engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        conn.execute(text(f"""
            CREATE TABLE {tbl} (
                id    SERIAL PRIMARY KEY,
                name  TEXT,
                value INTEGER
            )
        """))
        conn.commit()
    cdc.add_trigger_to_table(tbl)
    yield tbl
    with db_engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        conn.commit()


@pytest.fixture()
def uuid_pk_table(db_engine, cdc):
    """Temporary table with a UUID primary key."""
    tbl = "cdc_test_uuid_pk"
    with db_engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        conn.execute(text(f"""
            CREATE TABLE {tbl} (
                id    UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                label TEXT
            )
        """))
        conn.commit()
    cdc.add_trigger_to_table(tbl)
    yield tbl
    with db_engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        conn.commit()


@pytest.fixture()
def text_pk_table(db_engine, cdc):
    """Temporary table with a VARCHAR primary key."""
    tbl = "cdc_test_text_pk"
    with db_engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        conn.execute(text(f"""
            CREATE TABLE {tbl} (
                code  VARCHAR(50) PRIMARY KEY,
                descr TEXT
            )
        """))
        conn.commit()
    cdc.add_trigger_to_table(tbl)
    yield tbl
    with db_engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        conn.commit()


def _latest_log_row(engine, table_name: str) -> dict:
    """Helper: fetch most recent change_log row for a given table."""
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT change_id, table_name, operation, record_id,
                   old_data, new_data, changed_at, tenant_id
              FROM data_change_log
             WHERE table_name = :tbl
             ORDER BY change_id DESC
             LIMIT 1
        """), {"tbl": table_name}).fetchone()
    assert row is not None, f"No change-log row found for table '{table_name}'"
    return {
        "change_id":  row[0],
        "table_name": row[1],
        "operation":  row[2],
        "record_id":  row[3],
        "old_data":   row[4],
        "new_data":   row[5],
        "changed_at": row[6],
        "tenant_id":  row[7],
    }

# ═════════════════════════════════════════════════════════════════════════════
# GROUP 1 — Schema Correctness
# ═════════════════════════════════════════════════════════════════════════════

class TestSchema:

    def test_tenant_id_column_exists(self, db_engine, cdc):
        """data_change_log must have a tenant_id column."""
        with db_engine.connect() as conn:
            count = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns
                 WHERE table_name   = 'data_change_log'
                   AND column_name  = 'tenant_id'
                   AND table_schema = 'public'
            """)).scalar()
        assert count == 1, "tenant_id column missing from data_change_log"

    def test_record_id_is_text(self, db_engine, cdc):
        """record_id must be stored as TEXT (not INTEGER/BIGINT)."""
        with db_engine.connect() as conn:
            dtype = conn.execute(text("""
                SELECT data_type FROM information_schema.columns
                 WHERE table_name   = 'data_change_log'
                   AND column_name  = 'record_id'
                   AND table_schema = 'public'
            """)).scalar()
        assert dtype is not None, "record_id column not found"
        assert dtype.lower() in ("text", "character varying"), (
            f"record_id should be TEXT, got '{dtype}'"
        )

    def test_no_legacy_log_data_change_function(self, db_engine, cdc):
        """log_data_change must NOT exist — only log_table_changes is canonical."""
        with db_engine.connect() as conn:
            count = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.routines
                 WHERE routine_name   = 'log_data_change'
                   AND routine_schema = 'public'
            """)).scalar()
        assert count == 0, "Legacy function log_data_change still exists — must be dropped"

    def test_canonical_trigger_function_exists(self, db_engine, cdc):
        """log_table_changes must exist."""
        with db_engine.connect() as conn:
            count = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.routines
                 WHERE routine_name   = 'log_table_changes'
                   AND routine_schema = 'public'
            """)).scalar()
        assert count == 1, "Canonical trigger function log_table_changes missing"

    def test_cdc_config_table_exists(self, db_engine, cdc):
        """_cdc_config must exist after configure_tenant()."""
        with db_engine.connect() as conn:
            count = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables
                 WHERE table_name   = '_cdc_config'
                   AND table_schema = 'public'
            """)).scalar()
        assert count == 1

    def test_required_indexes_exist(self, db_engine, cdc):
        """Verify the three critical indexes are present."""
        expected = {
            "idx_change_log_id",
            "idx_change_log_tenant_time",
            "idx_change_log_table",
        }
        with db_engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT indexname FROM pg_indexes
                 WHERE tablename = 'data_change_log'
            """)).fetchall()
        found = {r[0] for r in rows}
        missing = expected - found
        assert not missing, f"Missing indexes: {missing}"

# ═════════════════════════════════════════════════════════════════════════════
# GROUP 2 — Integer PK Table (INSERT / UPDATE / DELETE)
# ═════════════════════════════════════════════════════════════════════════════

class TestIntegerPK:

    def test_insert_captured(self, db_engine, int_pk_table):
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('alpha', 10)"
            ))
            conn.commit()
        row = _latest_log_row(db_engine, int_pk_table)
        assert row["operation"] == "INSERT"
        assert row["record_id"] is not None
        assert row["new_data"] is not None
        assert row["old_data"] is None

    def test_insert_record_id_is_string(self, db_engine, int_pk_table):
        """record_id must be a string even for SERIAL PKs."""
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('beta', 20)"
            ))
            conn.commit()
        row = _latest_log_row(db_engine, int_pk_table)
        assert isinstance(row["record_id"], str), (
            f"record_id should be str, got {type(row['record_id'])}"
        )
        int(row["record_id"])  # must still be parseable as integer

    def test_update_has_old_and_new(self, db_engine, int_pk_table):
        with db_engine.connect() as conn:
            result = conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('gamma', 30) RETURNING id"
            ))
            row_id = result.scalar()
            conn.execute(text(
                f"UPDATE {int_pk_table} SET value = 99 WHERE id = :rid"
            ), {"rid": row_id})
            conn.commit()
        row = _latest_log_row(db_engine, int_pk_table)
        assert row["operation"] == "UPDATE"
        assert row["old_data"] is not None
        assert row["new_data"] is not None
        assert row["old_data"].get("value") == 30
        assert row["new_data"].get("value") == 99

    def test_delete_preserves_record_id(self, db_engine, int_pk_table):
        with db_engine.connect() as conn:
            result = conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('delta', 40) RETURNING id"
            ))
            row_id = result.scalar()
            conn.execute(text(
                f"DELETE FROM {int_pk_table} WHERE id = :rid"
            ), {"rid": row_id})
            conn.commit()
        row = _latest_log_row(db_engine, int_pk_table)
        assert row["operation"] == "DELETE"
        assert row["record_id"] == str(row_id)
        assert row["old_data"] is not None
        assert row["new_data"] is None


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 3 — UUID PK Table
# ═════════════════════════════════════════════════════════════════════════════

class TestUUIDPK:

    def test_insert_uuid_pk_stored_as_text(self, db_engine, uuid_pk_table):
        with db_engine.connect() as conn:
            result = conn.execute(text(
                f"INSERT INTO {uuid_pk_table} (label) VALUES ('uuid-row') RETURNING id"
            ))
            inserted_uuid = str(result.scalar())
            conn.commit()
        row = _latest_log_row(db_engine, uuid_pk_table)
        assert row["operation"] == "INSERT"
        assert isinstance(row["record_id"], str), "UUID pk must be stored as TEXT"
        assert row["record_id"] == inserted_uuid

    def test_update_uuid_row(self, db_engine, uuid_pk_table):
        with db_engine.connect() as conn:
            result = conn.execute(text(
                f"INSERT INTO {uuid_pk_table} (label) VALUES ('before') RETURNING id"
            ))
            uid = result.scalar()
            conn.execute(text(
                f"UPDATE {uuid_pk_table} SET label = 'after' WHERE id = :uid"
            ), {"uid": uid})
            conn.commit()
        row = _latest_log_row(db_engine, uuid_pk_table)
        assert row["operation"] == "UPDATE"
        assert row["old_data"]["label"] == "before"
        assert row["new_data"]["label"] == "after"

    def test_delete_uuid_row(self, db_engine, uuid_pk_table):
        with db_engine.connect() as conn:
            result = conn.execute(text(
                f"INSERT INTO {uuid_pk_table} (label) VALUES ('to-delete') RETURNING id"
            ))
            uid = str(result.scalar())
            conn.execute(text(
                f"DELETE FROM {uuid_pk_table} WHERE id = :uid"
            ), {"uid": uid})
            conn.commit()
        row = _latest_log_row(db_engine, uuid_pk_table)
        assert row["operation"] == "DELETE"
        assert row["record_id"] == uid

# ═════════════════════════════════════════════════════════════════════════════
# GROUP 4 — Text PK Table
# ═════════════════════════════════════════════════════════════════════════════

class TestTextPK:

    def test_insert_text_pk(self, db_engine, text_pk_table):
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {text_pk_table} (code, descr) VALUES ('CODE-001', 'First')"
            ))
            conn.commit()
        row = _latest_log_row(db_engine, text_pk_table)
        assert row["operation"] == "INSERT"
        assert row["record_id"] == "CODE-001"

    def test_update_text_pk(self, db_engine, text_pk_table):
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {text_pk_table} (code, descr) VALUES ('CODE-002', 'Old')"
            ))
            conn.execute(text(
                f"UPDATE {text_pk_table} SET descr = 'New' WHERE code = 'CODE-002'"
            ))
            conn.commit()
        row = _latest_log_row(db_engine, text_pk_table)
        assert row["operation"] == "UPDATE"
        assert row["record_id"] == "CODE-002"
        assert row["old_data"]["descr"] == "Old"
        assert row["new_data"]["descr"] == "New"

    def test_delete_text_pk(self, db_engine, text_pk_table):
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {text_pk_table} (code, descr) VALUES ('CODE-DEL', 'Bye')"
            ))
            conn.execute(text(
                f"DELETE FROM {text_pk_table} WHERE code = 'CODE-DEL'"
            ))
            conn.commit()
        row = _latest_log_row(db_engine, text_pk_table)
        assert row["operation"] == "DELETE"
        assert row["record_id"] == "CODE-DEL"


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 5 — Tenant Tracking
# ═════════════════════════════════════════════════════════════════════════════

class TestTenantTracking:

    def test_tenant_id_in_change_row(self, db_engine, int_pk_table, cdc):
        """Every change row must carry the configured tenant_id."""
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('tenant-test', 1)"
            ))
            conn.commit()
        row = _latest_log_row(db_engine, int_pk_table)
        assert row["tenant_id"] == TEST_TENANT_ID, (
            f"Expected tenant_id={TEST_TENANT_ID}, got {row['tenant_id']}"
        )

    def test_tenant_id_reconfiguration(self, db_engine, cdc, int_pk_table):
        """After reconfiguring to a new tenant_id, new rows must carry the new value."""
        new_tenant = 99
        cdc.configure_tenant(new_tenant)
        try:
            with db_engine.connect() as conn:
                conn.execute(text(
                    f"INSERT INTO {int_pk_table} (name, value) VALUES ('new-tenant', 2)"
                ))
                conn.commit()
            row = _latest_log_row(db_engine, int_pk_table)
            assert row["tenant_id"] == new_tenant
        finally:
            # restore original tenant for remaining tests
            cdc.configure_tenant(TEST_TENANT_ID)

    def test_get_changes_since_tenant_filter(self, db_engine, cdc, int_pk_table):
        """get_changes_since with tenant_id filter must exclude other tenants."""
        # Insert as tenant 42
        cdc.configure_tenant(42)
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('t42', 42)"
            ))
            conn.commit()
        hwm_42 = cdc.get_latest_change_id() or 0

        # Insert as tenant 77
        cdc.configure_tenant(77)
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('t77', 77)"
            ))
            conn.commit()

        # Filter for tenant 77 only — must NOT include tenant 42's row
        changes = cdc.get_changes_since(hwm_42, tenant_id=77)
        assert all(c["tenant_id"] == 77 for c in changes), (
            "get_changes_since with tenant_id=77 returned rows for wrong tenant"
        )
        # Restore
        cdc.configure_tenant(TEST_TENANT_ID)

# ═════════════════════════════════════════════════════════════════════════════
# GROUP 6 — Cursor-Based Retrieval (get_changes_since)
# ═════════════════════════════════════════════════════════════════════════════

class TestCursorRetrieval:

    def test_returns_only_new_changes(self, db_engine, cdc, int_pk_table):
        """Changes before the watermark must NOT appear in results."""
        # Record current high-water-mark
        hwm = cdc.get_latest_change_id() or 0

        # Insert two rows AFTER the watermark
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('c1', 1)"
            ))
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('c2', 2)"
            ))
            conn.commit()

        changes = cdc.get_changes_since(hwm)
        assert len(changes) >= 2

    def test_ordered_ascending(self, db_engine, cdc, int_pk_table):
        """Results must be ordered change_id ASC."""
        hwm = cdc.get_latest_change_id() or 0
        with db_engine.connect() as conn:
            for i in range(5):
                conn.execute(text(
                    f"INSERT INTO {int_pk_table} (name, value) VALUES (:n, :v)"
                ), {"n": f"ord-{i}", "v": i})
            conn.commit()
        changes = cdc.get_changes_since(hwm)
        ids = [c["change_id"] for c in changes]
        assert ids == sorted(ids), "get_changes_since results not ordered ASC"

    def test_incremental_cursor_correctness(self, db_engine, cdc, int_pk_table):
        """
        Simulate two polling cycles.
        Cycle 1 captures first batch; cycle 2 captures only the second batch.
        """
        hwm0 = cdc.get_latest_change_id() or 0

        # Batch 1
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('batch1-a', 10)"
            ))
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('batch1-b', 11)"
            ))
            conn.commit()

        batch1 = cdc.get_changes_since(hwm0)
        assert len(batch1) >= 2
        hwm1 = batch1[-1]["change_id"]

        # Batch 2 (single row)
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('batch2', 20)"
            ))
            conn.commit()

        batch2 = cdc.get_changes_since(hwm1)
        assert len(batch2) >= 1
        batch2_names = [c["new_data"]["name"] for c in batch2 if c.get("new_data")]
        assert "batch2" in batch2_names

        # Batch 1 rows must NOT appear in batch 2
        batch1_ids = {c["change_id"] for c in batch1}
        batch2_ids = {c["change_id"] for c in batch2}
        overlap = batch1_ids & batch2_ids
        assert not overlap, f"Cursor overlap: change_ids {overlap} appeared in both batches"

    def test_empty_result_when_no_new_changes(self, db_engine, cdc):
        """If nothing happened since the watermark, return empty list."""
        hwm = cdc.get_latest_change_id() or 0
        result = cdc.get_changes_since(hwm)
        assert result == [], "Expected empty list when no new changes"

    def test_no_limit_applied(self, db_engine, cdc, int_pk_table):
        """get_changes_since must NOT apply a default LIMIT."""
        hwm = cdc.get_latest_change_id() or 0
        N = 120   # more than the old get_recent_changes default of 100
        with db_engine.connect() as conn:
            for i in range(N):
                conn.execute(text(
                    f"INSERT INTO {int_pk_table} (name, value) VALUES (:n, :v)"
                ), {"n": f"nolimit-{i}", "v": i})
            conn.commit()
        changes = cdc.get_changes_since(hwm)
        assert len(changes) >= N, (
            f"get_changes_since returned only {len(changes)} rows; "
            f"expected at least {N} (no default LIMIT should be applied)"
        )

# ═════════════════════════════════════════════════════════════════════════════
# GROUP 7 — SQL Injection Protection
# ═════════════════════════════════════════════════════════════════════════════

class TestSQLInjection:

    def test_invalid_table_raises_value_error(self, cdc):
        """A totally fake table must raise ValueError before any SQL runs."""
        with pytest.raises(ValueError, match="not found in schema"):
            cdc.add_trigger_to_table("nonexistent_table_xyz")

    def test_injection_attempt_raises_value_error(self, cdc):
        """Classic injection suffix must be caught by the whitelist."""
        with pytest.raises(ValueError):
            cdc.add_trigger_to_table("patients; DROP TABLE patients; --")

    def test_injection_with_quotes_raises_value_error(self, cdc):
        """Quote-based injection must also be blocked."""
        with pytest.raises(ValueError):
            cdc.add_trigger_to_table("patients' OR '1'='1")

    def test_empty_name_raises_value_error(self, cdc):
        """Empty string must be blocked."""
        with pytest.raises(ValueError):
            cdc.add_trigger_to_table("")

    def test_valid_table_does_not_raise(self, db_engine, cdc):
        """A legitimately existing table must succeed without errors."""
        tbl = "cdc_injection_safe_test"
        with db_engine.connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
            conn.execute(text(f"""
                CREATE TABLE {tbl} (
                    id    SERIAL PRIMARY KEY,
                    label TEXT
                )
            """))
            conn.commit()
        try:
            cdc.add_trigger_to_table(tbl)   # must not raise
        finally:
            with db_engine.connect() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
                conn.commit()


# ═════════════════════════════════════════════════════════════════════════════
# GROUP 8 — Backward Compatibility
# ═════════════════════════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    """Ensure the existing public API still works so connector.py isn't broken."""

    def test_get_recent_changes_returns_list(self, cdc):
        result = cdc.get_recent_changes(limit=10)
        assert isinstance(result, list)

    def test_get_recent_changes_row_shape(self, db_engine, cdc, int_pk_table):
        """Every row must have the 8 expected keys."""
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('compat', 1)"
            ))
            conn.commit()
        rows = cdc.get_recent_changes(table_name=int_pk_table, limit=1)
        assert len(rows) >= 1
        expected_keys = {
            "change_id", "table_name", "operation", "record_id",
            "old_data", "new_data", "changed_at", "tenant_id",
        }
        assert expected_keys == set(rows[0].keys()), (
            f"Row shape mismatch. Got: {set(rows[0].keys())}"
        )

    def test_get_recent_changes_table_filter(self, db_engine, cdc, int_pk_table):
        """table_name filter must restrict rows to that table only."""
        with db_engine.connect() as conn:
            conn.execute(text(
                f"INSERT INTO {int_pk_table} (name, value) VALUES ('filter-test', 5)"
            ))
            conn.commit()
        rows = cdc.get_recent_changes(table_name=int_pk_table, limit=50)
        assert all(r["table_name"] == int_pk_table for r in rows)

    def test_get_change_statistics_returns_dict(self, cdc):
        stats = cdc.get_change_statistics()
        assert isinstance(stats, dict)

    def test_get_latest_change_id_returns_int_or_none(self, cdc):
        hwm = cdc.get_latest_change_id()
        assert hwm is None or isinstance(hwm, int)
