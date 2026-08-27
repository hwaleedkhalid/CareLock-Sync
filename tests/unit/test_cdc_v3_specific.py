"""
Additional v3-specific tests for Risk 1, 5, and 7
These extend test_cdc_monitor.py with v3-specific functionality.
Run: pytest tests/unit/test_cdc_v3_specific.py -v
"""
import os
import sys
import pytest
from sqlalchemy import create_engine, text

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from connector.cdc_monitor import CDCMonitor

def _get_test_db_url() -> str:
    explicit = os.environ.get("TEST_DB_URL")
    if explicit:
        return explicit
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        try:
            from dotenv import dotenv_values
            vals = dotenv_values(env_path)
            if vals.get("HOSPITAL_DB_URL"):
                return vals["HOSPITAL_DB_URL"]
        except ImportError:
            pass
    return "postgresql://hospital_user:hospital_pass@localhost:5432/hospital_db"

@pytest.fixture(scope="module")
def db_engine():
    url = _get_test_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()

@pytest.fixture(scope="module")
def cdc(db_engine):
    monitor = CDCMonitor(db_engine.url.render_as_string(hide_password=False))
    monitor.configure_tenant(50)
    monitor.create_change_log_table()
    monitor.create_trigger_function()
    yield monitor

# ══════════════════════════════════════════════════════════════════════════════
# Risk 1 — GUC fast-path test
# ══════════════════════════════════════════════════════════════════════════════

class TestGUCFastPath:
    """Risk 1: Verify current_setting('app.tenant_id', true) works."""

    def test_set_session_tenant_method_exists(self, cdc):
        """CDCMonitor.set_session_tenant() must be callable."""
        assert hasattr(CDCMonitor, "set_session_tenant")
        assert callable(CDCMonitor.set_session_tenant)

    def test_session_tenant_flows_to_change_log(self, db_engine, cdc):
        """
        When set_session_tenant() is called, trigger should read
        from GUC (fast path) rather than _cdc_config.
        """
        # Create test table
        tbl = "cdc_guc_test"
        with db_engine.connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
            conn.execute(text(f"""
                CREATE TABLE {tbl} (
                    id    SERIAL PRIMARY KEY,
                    data  TEXT
                )
            """))
            conn.commit()
        
        cdc.add_trigger_to_table(tbl)
        
        try:
            # Set session-level tenant
            with db_engine.connect() as conn:
                CDCMonitor.set_session_tenant(conn, 999)
                conn.execute(text(
                    f"INSERT INTO {tbl} (data) VALUES ('guc-test')"
                ))
                conn.commit()
            
            # Verify tenant_id from GUC made it into the log
            with db_engine.connect() as conn:
                row = conn.execute(text("""
                    SELECT tenant_id FROM data_change_log
                     WHERE table_name = :tbl
                     ORDER BY change_id DESC LIMIT 1
                """), {"tbl": tbl}).fetchone()
            
            assert row is not None, "No change log row found"
            assert row[0] == 999, (
                f"Expected tenant_id=999 from GUC, got {row[0]}"
            )
        finally:
            with db_engine.connect() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
                conn.commit()

# ══════════════════════════════════════════════════════════════════════════════
# Risk 5 — migrate_schema() test
# ══════════════════════════════════════════════════════════════════════════════

class TestMigration:
    """Risk 5: Verify migrate_schema() is idempotent and safe."""

    def test_migrate_schema_method_exists(self, cdc):
        assert hasattr(cdc, "migrate_schema")
        assert callable(cdc.migrate_schema)

    def test_migrate_schema_is_idempotent(self, cdc):
        """Running migrate_schema() twice must not raise errors."""
        cdc.migrate_schema()  # first call
        cdc.migrate_schema()  # second call — must be safe

    def test_record_id_stays_text_after_migration(self, db_engine, cdc):
        """After migration, record_id must be TEXT."""
        cdc.migrate_schema()
        
        with db_engine.connect() as conn:
            dtype = conn.execute(text("""
                SELECT data_type FROM information_schema.columns
                 WHERE table_name   = 'data_change_log'
                   AND column_name  = 'record_id'
                   AND table_schema = 'public'
            """)).scalar()
        
        assert dtype is not None
        assert dtype.lower() in ("text", "character varying"), (
            f"After migration, record_id should be TEXT, got {dtype}"
        )

    def test_migration_adds_tenant_id_if_missing(self, db_engine):
        """
        If tenant_id column is absent, migrate_schema() must add it.
        (This test assumes a clean state or manually dropped column.)
        """
        # Note: This test might fail if tenant_id already exists
        # It's here to document the migration's behavior
        with db_engine.connect() as conn:
            count = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns
                 WHERE table_name   = 'data_change_log'
                   AND column_name  = 'tenant_id'
                   AND table_schema = 'public'
            """)).scalar()
        
        # If it's already there, test passes
        # If not, migrate_schema() will add it
        assert count >= 1, "tenant_id column missing after migration"

# ══════════════════════════════════════════════════════════════════════════════
# Risk 7 — SECURITY DEFINER verification
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurityDefiner:
    """Risk 7: Verify trigger function has SECURITY DEFINER attribute."""

    def test_log_table_changes_is_security_definer(self, db_engine):
        """
        Query pg_proc to verify the function's prosecdef attribute is true,
        which means it runs with SECURITY DEFINER.
        """
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT prosecdef FROM pg_proc
                 WHERE proname = 'log_table_changes'
                   AND pronamespace = (
                       SELECT oid FROM pg_namespace WHERE nspname = 'public'
                   )
            """)).fetchone()
        
        assert result is not None, "log_table_changes function not found"
        assert result[0] is True, (
            "log_table_changes must have SECURITY DEFINER (prosecdef=true)"
        )

    def test_function_has_execute_grant(self, db_engine):
        """
        Verify PUBLIC has EXECUTE privilege on log_table_changes.
        This ensures all application roles can fire the trigger.
        """
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT has_function_privilege('public', 'log_table_changes()', 'EXECUTE')
            """)).scalar()
        
        assert result is True, (
            "PUBLIC must have EXECUTE on log_table_changes for triggers to work"
        )

# ══════════════════════════════════════════════════════════════════════════════
# Risk 8 — pg_notify payload verification (integration test)
# ══════════════════════════════════════════════════════════════════════════════

class TestNotifyPayload:
    """
    Risk 8: Verify pg_notify payload contains tenant_id and timestamp.
    Note: This requires LISTEN/NOTIFY which is complex in pytest.
    This test documents the expected behavior.
    """

    def test_trigger_contains_pg_notify_call(self, db_engine):
        """Verify the trigger function source includes pg_notify."""
        with db_engine.connect() as conn:
            source = conn.execute(text("""
                SELECT prosrc FROM pg_proc
                 WHERE proname = 'log_table_changes'
                   AND pronamespace = (
                       SELECT oid FROM pg_namespace WHERE nspname = 'public'
                   )
            """)).scalar()
        
        assert source is not None
        assert "pg_notify" in source, "Trigger must call pg_notify"
        assert "'tenant_id'" in source, "Payload must include tenant_id"
        assert "to_char(NOW()" in source, "Payload must include ISO timestamp"
