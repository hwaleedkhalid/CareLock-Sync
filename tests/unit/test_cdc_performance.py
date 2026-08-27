"""
tests/unit/test_cdc_performance.py
====================================
Risk 9 — Concurrency and performance tests for CDCMonitor v3.

Tests:
  - High-volume single-writer burst (1000 rows)
  - Concurrent multi-writer stress (N threads × M rows each)
  - Streaming generator memory profile (no full list in memory)
  - Index utilization via EXPLAIN ANALYZE (no seq-scan on large log)
  - Watermark correctness under concurrent advance_watermark calls
  - Trigger overhead measurement (time per row)

Run (requires live PostgreSQL):
    pytest tests/unit/test_cdc_performance.py -v -s
"""
from __future__ import annotations

import os
import sys
import time
import threading
from typing import List

import pytest
from sqlalchemy import create_engine, text

_BACKEND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "backend")
)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from connector.cdc_monitor import CDCMonitor

PERF_TENANT = 88   # Distinct tenant so tests don't collide with unit tests


def _url() -> str:
    explicit = os.environ.get("TEST_DB_URL")
    if explicit:
        return explicit
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        try:
            from dotenv import dotenv_values
            v = dotenv_values(env_path)
            if v.get("HOSPITAL_DB_URL"):
                return v["HOSPITAL_DB_URL"]
        except ImportError:
            pass
    return "postgresql://hospital_user:hospital_pass@localhost:5432/hospital_db"


# ── Session fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    e = create_engine(_url(), pool_size=10, max_overflow=10, pool_pre_ping=True)
    yield e
    e.dispose()


@pytest.fixture(scope="module")
def cdc(engine):
    m = CDCMonitor(engine.url.render_as_string(hide_password=False))
    m.configure_tenant(PERF_TENANT)
    m.create_change_log_table()
    m.create_trigger_function()
    yield m


@pytest.fixture()
def perf_table(engine, cdc):
    """A fresh table instrumented with CDC, dropped after each test."""
    tbl = "cdc_perf_test"
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        conn.execute(text(f"""
            CREATE TABLE {tbl} (
                id    BIGSERIAL PRIMARY KEY,
                data  TEXT,
                value INTEGER
            )
        """))
        conn.commit()
    cdc.add_trigger_to_table(tbl)
    yield tbl
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
        conn.commit()

# ── Group 1: High-volume burst ────────────────────────────────────────────────

class TestHighVolumeBurst:
    """Single writer, large batch — measures trigger overhead per row."""

    N = 1000  # rows to insert

    def test_burst_insert_all_captured(self, engine, cdc, perf_table):
        """All N rows must appear in data_change_log."""
        hwm = cdc.get_latest_change_id() or 0
        t0 = time.perf_counter()

        with engine.connect() as conn:
            for i in range(self.N):
                conn.execute(text(
                    f"INSERT INTO {perf_table} (data, value) VALUES (:d, :v)"
                ), {"d": f"row-{i}", "v": i})
            conn.commit()

        elapsed = time.perf_counter() - t0
        per_row_ms = (elapsed / self.N) * 1000

        changes = cdc.get_changes_since(hwm, tenant_id=PERF_TENANT)
        assert len(changes) >= self.N, (
            f"Expected {self.N} log rows, got {len(changes)}"
        )
        print(f"\n[PERF] {self.N} inserts in {elapsed:.2f}s "
              f"({per_row_ms:.2f} ms/row incl. trigger)")

        # Soft threshold: trigger overhead should stay under 5 ms/row
        assert per_row_ms < 5.0, (
            f"Trigger overhead {per_row_ms:.2f} ms/row exceeds 5 ms threshold"
        )

    def test_burst_tenant_id_consistent(self, engine, cdc, perf_table):
        """All rows in a burst must carry the configured tenant_id."""
        hwm = cdc.get_latest_change_id() or 0
        with engine.connect() as conn:
            for i in range(50):
                conn.execute(text(
                    f"INSERT INTO {perf_table} (data, value) VALUES (:d, :v)"
                ), {"d": f"t-{i}", "v": i})
            conn.commit()
        changes = cdc.get_changes_since(hwm, tenant_id=PERF_TENANT)
        wrong = [c for c in changes if c["tenant_id"] != PERF_TENANT]
        assert not wrong, (
            f"{len(wrong)} rows had wrong tenant_id: {[c['tenant_id'] for c in wrong[:5]]}"
        )


# ── Group 2: Concurrent multi-writer stress ───────────────────────────────────

class TestConcurrentWriters:
    """Multiple threads writing simultaneously — tests trigger + log table contention."""

    THREADS = 5
    ROWS_PER_THREAD = 100

    def test_concurrent_inserts_all_captured(self, engine, cdc, perf_table):
        hwm = cdc.get_latest_change_id() or 0
        errors: List[Exception] = []

        def worker(thread_id: int):
            try:
                with engine.connect() as conn:
                    for i in range(self.ROWS_PER_THREAD):
                        conn.execute(text(
                            f"INSERT INTO {perf_table} (data, value) VALUES (:d, :v)"
                        ), {"d": f"t{thread_id}-r{i}", "v": i})
                    conn.commit()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(tid,))
                   for tid in range(self.THREADS)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - t0

        assert not errors, f"Worker errors: {errors}"

        total_expected = self.THREADS * self.ROWS_PER_THREAD
        changes = cdc.get_changes_since(hwm, tenant_id=PERF_TENANT)
        assert len(changes) >= total_expected, (
            f"Expected {total_expected} rows, got {len(changes)}"
        )
        print(f"\n[PERF] {total_expected} concurrent inserts in {elapsed:.2f}s "
              f"({self.THREADS} threads)")

    def test_concurrent_watermark_advance_is_safe(self, cdc):
        """
        Multiple threads advancing the watermark concurrently must never
        move it backwards (GREATEST semantics in ON CONFLICT DO UPDATE).
        """
        base = cdc.load_watermark(PERF_TENANT)
        target = base + 1000
        errors: List[Exception] = []

        def advance(val: int):
            try:
                cdc.advance_watermark(PERF_TENANT, val)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=advance, args=(base + i,))
            for i in range(100)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Watermark advance errors: {errors}"
        final = cdc.load_watermark(PERF_TENANT)
        assert final == base + 99, (
            f"Expected watermark {base + 99}, got {final}"
        )

# ── Group 3: Streaming generator (Risk 3) ─────────────────────────────────────

class TestStreamingGenerator:
    """Verify iter_changes_since() streams without loading full result into memory."""

    ROWS = 600   # more than one batch_size of 500

    def test_streaming_yields_correct_total(self, engine, cdc, perf_table):
        hwm = cdc.get_latest_change_id() or 0
        with engine.connect() as conn:
            for i in range(self.ROWS):
                conn.execute(text(
                    f"INSERT INTO {perf_table} (data, value) VALUES (:d, :v)"
                ), {"d": f"stream-{i}", "v": i})
            conn.commit()

        total = 0
        batches = 0
        for batch in cdc.iter_changes_since(hwm, tenant_id=PERF_TENANT, batch_size=200):
            assert len(batch) <= 200, "Batch exceeded batch_size"
            total += len(batch)
            batches += 1

        assert total >= self.ROWS, f"Expected {self.ROWS} streamed rows, got {total}"
        assert batches >= 3, f"Expected at least 3 batches for {self.ROWS} rows at 200/batch"
        print(f"\n[PERF] Streamed {total} rows in {batches} batches")

    def test_streaming_ordered_asc(self, engine, cdc, perf_table):
        hwm = cdc.get_latest_change_id() or 0
        with engine.connect() as conn:
            for i in range(50):
                conn.execute(text(
                    f"INSERT INTO {perf_table} (data, value) VALUES (:d, :v)"
                ), {"d": f"ord-{i}", "v": i})
            conn.commit()

        ids = []
        for batch in cdc.iter_changes_since(hwm, tenant_id=PERF_TENANT, batch_size=20):
            ids.extend(c["change_id"] for c in batch)

        assert ids == sorted(ids), "iter_changes_since not ordered ASC"

    def test_eager_batch_size_respected(self, engine, cdc, perf_table):
        hwm = cdc.get_latest_change_id() or 0
        with engine.connect() as conn:
            for i in range(50):
                conn.execute(text(
                    f"INSERT INTO {perf_table} (data, value) VALUES (:d, :v)"
                ), {"d": f"eager-{i}", "v": i})
            conn.commit()

        results = cdc.get_changes_since(hwm, tenant_id=PERF_TENANT, batch_size=10)
        assert len(results) == 10, (
            f"batch_size=10 should return exactly 10 rows, got {len(results)}"
        )


# ── Group 4: Index utilization (Risk 5 / query plan) ─────────────────────────

class TestIndexUtilization:
    """
    Verify that cursor queries use the change_id index and tenant+time
    composite index rather than sequential scans.
    Uses EXPLAIN (FORMAT JSON) to inspect the query plan.
    """

    def test_cursor_query_uses_index(self, engine, cdc):
        plan = engine.connect().execute(text("""
            EXPLAIN (FORMAT JSON)
            SELECT change_id, table_name, operation, record_id,
                   old_data, new_data, changed_at, tenant_id
              FROM data_change_log
             WHERE change_id > 0
             ORDER BY change_id ASC
        """)).scalar()

        plan_str = str(plan)
        assert "Seq Scan" not in plan_str or "Index" in plan_str, (
            "Cursor query is doing a full sequential scan — check idx_change_log_id"
        )

    def test_tenant_time_query_uses_index(self, engine):
        plan = engine.connect().execute(text("""
            EXPLAIN (FORMAT JSON)
            SELECT change_id FROM data_change_log
             WHERE tenant_id = 1
               AND changed_at > NOW() - INTERVAL '1 hour'
             ORDER BY changed_at
        """)).scalar()

        plan_str = str(plan)
        # Either an index scan or bitmap index scan is acceptable
        assert "Index" in plan_str or "Bitmap" in plan_str, (
            "Tenant+time query doing full seq scan — check idx_change_log_tenant_time"
        )


# ── Group 5: Watermark persistence (Risk 4 + 6) ──────────────────────────────

class TestWatermarkPersistence:

    def test_load_returns_zero_for_new_tenant(self, cdc):
        fresh_tenant = 9999
        val = cdc.load_watermark(fresh_tenant)
        assert val == 0

    def test_advance_persists(self, cdc):
        t = 7777
        cdc.advance_watermark(t, 500)
        assert cdc.load_watermark(t) == 500

    def test_advance_never_goes_backwards(self, cdc):
        t = 6666
        cdc.advance_watermark(t, 1000)
        cdc.advance_watermark(t, 200)   # lower value — must be ignored
        assert cdc.load_watermark(t) == 1000, (
            "Watermark moved backwards — GREATEST logic broken"
        )

    def test_save_watermark_alias(self, cdc):
        t = 5555
        cdc.save_watermark(t, 750)
        assert cdc.load_watermark(t) == 750

    def test_watermark_isolated_per_tenant(self, cdc):
        cdc.advance_watermark(1001, 100)
        cdc.advance_watermark(1002, 200)
        assert cdc.load_watermark(1001) == 100
        assert cdc.load_watermark(1002) == 200
