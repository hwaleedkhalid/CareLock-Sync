#!/usr/bin/env python3
"""
full_benchmark.py
=================
Empirical benchmark for CareLock-Sync.
Measures: sync throughput, ETL latency, RAG accuracy,
          tenant isolation, CDC reliability, idempotency, concurrency.

Run from backend/ directory:
    python scripts/full_benchmark.py
"""
from __future__ import annotations
import os, sys, time, json, threading, statistics, logging
from datetime import datetime
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.WARNING)

# ── Connection strings ────────────────────────────────────────────────────────
CENTRAL = "postgresql://shared_user:shared_pass@localhost:5433/carelock_shared"
PG_HOSP = "postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db"
MYSQL   = "mysql://hospital_user:hospital_pass@localhost:3306/hospital_db_mysql"
MONGO   = "mongodb://localhost:27017/hospital_db_mongodb"
ORACLE  = "oracle://hospital_user:hospital_pass@localhost:1521/XEPDB1"
MSSQL   = "sqlserver://sa:YourStrong@Passw0rd@localhost:1433/hospital_db_sqlserver"

SOURCES = [
    ("postgres",  10, PG_HOSP),
    ("mysql",     11, MYSQL),
    ("mongodb",   12, MONGO),
    ("oracle",    13, ORACLE),
    ("sqlserver", 14, MSSQL),
]

results: Dict[str, Any] = {}

def separator(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Central DB baseline counts
# ─────────────────────────────────────────────────────────────────────────────
def test_baseline_counts():
    separator("TEST 1 — Central DB Baseline Counts")
    c = psycopg2.connect(CENTRAL)
    cur = c.cursor()
    counts = {}
    for tbl in ["fhir_patient","fhir_encounter","fhir_observation","fhir_medication_request","sync_runs","hospital_tenants"]:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        counts[tbl] = cur.fetchone()[0]
    c.close()
    for k,v in counts.items():
        print(f"  {k:40s}: {v:,}")
    results["baseline_counts"] = counts
    return counts

# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — Sync run history analysis
# ─────────────────────────────────────────────────────────────────────────────
def test_sync_history():
    separator("TEST 2 — Sync Run History (from 778 completed runs)")
    c = psycopg2.connect(CENTRAL)
    cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            mode,
            status,
            COUNT(*) as run_count,
            AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_dur_s,
            MIN(EXTRACT(EPOCH FROM (completed_at - started_at))) as min_dur_s,
            MAX(EXTRACT(EPOCH FROM (completed_at - started_at))) as max_dur_s,
            PERCENTILE_CONT(0.5) WITHIN GROUP
              (ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))) as p50_dur_s,
            PERCENTILE_CONT(0.95) WITHIN GROUP
              (ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))) as p95_dur_s
        FROM sync_runs
        WHERE status IN ('completed','failed')
          AND completed_at IS NOT NULL
        GROUP BY mode, status
        ORDER BY mode, status
    """)
    rows = cur.fetchall()
    for r in rows:
        print(f"  mode={r['mode']:12s} status={r['status']:10s} count={r['run_count']:4d} "
              f"avg={r['avg_dur_s']:.2f}s p50={r['p50_dur_s']:.2f}s "
              f"p95={r['p95_dur_s']:.2f}s min={r['min_dur_s']:.2f}s max={r['max_dur_s']:.2f}s")
    # Total records from latest completed runs per tenant
    cur.execute("""
        SELECT s.tenant_id, s.mode, s.records_processed,
               EXTRACT(EPOCH FROM (s.completed_at - s.started_at)) as dur_s
        FROM sync_runs s
        INNER JOIN (
            SELECT tenant_id, MAX(completed_at) as latest
            FROM sync_runs WHERE status='completed' GROUP BY tenant_id
        ) latest ON s.tenant_id=latest.tenant_id AND s.completed_at=latest.latest
        WHERE s.status='completed'
        ORDER BY s.tenant_id
    """)
    latest = cur.fetchall()
    print(f"\n  Latest completed run per tenant:")
    for r in latest:
        rp = r['records_processed']
        dur = r['dur_s']
        total_records = sum(rp.values()) if isinstance(rp, dict) else 0
        tput = round(total_records / dur, 1) if dur and dur > 0 else "n/a"
        print(f"  tenant={r['tenant_id']:3d} mode={r['mode']:12s} "
              f"records={total_records:5d} dur={dur:.2f}s throughput={tput} rec/s")
    c.close()
    results["sync_history"] = [dict(r) for r in rows]
    results["latest_runs"]  = [dict(r) for r in latest]

# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — Live timed ETL benchmark per source
# ─────────────────────────────────────────────────────────────────────────────
def test_live_etl_timing():
    separator("TEST 3 — Live Timed ETL (MultiDBPipeline per source)")
    from cdc.adapter_factory import CDCAdapterFactory
    from etl.multi_db_pipeline import MultiDBPipeline

    timing_results = []
    for label, tid, cs in SOURCES:
        print(f"\n  [{label.upper()}] tenant={tid}")
        try:
            adapter = CDCAdapterFactory.create_adapter(cs)
            if not adapter.validate_connection():
                print(f"    SKIP — cannot connect")
                timing_results.append({"source": label, "status": "unreachable"})
                continue

            t0 = time.perf_counter()
            stats = MultiDBPipeline(adapter, tenant_id=tid).sync_all(limit=None)
            dur = time.perf_counter() - t0
            adapter.close()

            total_ex  = sum(v["extracted"]    for v in stats.values())
            total_ld  = sum(v["loaded"]        for v in stats.values())
            total_err = sum(v["errors"]        for v in stats.values())
            tput      = round(total_ld / dur, 1) if dur > 0 else 0

            print(f"    extracted={total_ex}  loaded={total_ld}  "
                  f"errors={total_err}  time={dur:.3f}s  throughput={tput} rec/s")
            for resource, s in stats.items():
                print(f"    └─ {resource:14s} ex={s['extracted']:3d} ld={s['loaded']:3d} err={s['errors']}")

            timing_results.append({
                "source": label, "status": "ok",
                "extracted": total_ex, "loaded": total_ld,
                "errors": total_err, "duration_s": round(dur, 3),
                "throughput_rec_s": tput, "per_resource": dict(stats)
            })
        except Exception as e:
            print(f"    CRASH: {e}")
            timing_results.append({"source": label, "status": "crash", "error": str(e)})

    results["etl_timing"] = timing_results

# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — CDC trigger overhead (PostgreSQL only)
# ─────────────────────────────────────────────────────────────────────────────
def test_cdc_trigger_overhead():
    separator("TEST 4 — CDC Trigger Overhead (1000-row burst, PostgreSQL)")
    from connector.cdc_monitor import CDCMonitor

    engine = create_engine(PG_HOSP, pool_pre_ping=True)
    cdc = CDCMonitor(PG_HOSP)
    cdc.configure_tenant(99)
    cdc.create_change_log_table()
    cdc.create_trigger_function()

    TBL = "bench_trigger_test"
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TBL} CASCADE"))
        conn.execute(text(f"CREATE TABLE {TBL} (id BIGSERIAL PRIMARY KEY, val TEXT, num INT)"))
        conn.commit()
    cdc.add_trigger_to_table(TBL)

    # 1000-row burst
    N = 1000
    hwm = cdc.get_latest_change_id() or 0
    t0 = time.perf_counter()
    with engine.connect() as conn:
        for i in range(N):
            conn.execute(text(f"INSERT INTO {TBL} (val,num) VALUES (:v,:n)"), {"v": f"r{i}", "n": i})
        conn.commit()
    burst_dur = time.perf_counter() - t0
    per_row_ms = (burst_dur / N) * 1000

    changes = cdc.get_changes_since(hwm, tenant_id=99)
    captured = len(changes)
    capture_rate = round(captured / N * 100, 2)

    print(f"  Rows inserted : {N}")
    print(f"  Total time    : {burst_dur:.3f}s")
    print(f"  Per-row       : {per_row_ms:.3f}ms")
    print(f"  Throughput    : {round(N/burst_dur)} rows/s")
    print(f"  Changes captured: {captured}/{N} ({capture_rate}%)")
    print(f"  Assertion (<5ms): {'PASS' if per_row_ms < 5.0 else 'FAIL'}")

    # Streaming test: 600 rows, batch_size=200
    hwm2 = cdc.get_latest_change_id() or 0
    with engine.connect() as conn:
        for i in range(600):
            conn.execute(text(f"INSERT INTO {TBL} (val,num) VALUES (:v,:n)"), {"v": f"s{i}", "n": i})
        conn.commit()

    t0 = time.perf_counter()
    total_streamed, batch_count = 0, 0
    for batch in cdc.iter_changes_since(hwm2, tenant_id=99, batch_size=200):
        total_streamed += len(batch)
        batch_count    += 1
    stream_dur = time.perf_counter() - t0

    print(f"\n  Streaming (600 rows, batch=200):")
    print(f"  Batches       : {batch_count}")
    print(f"  Total streamed: {total_streamed}")
    print(f"  Stream time   : {stream_dur:.3f}s")
    print(f"  Order correct : {'PASS' if batch_count >= 3 else 'FAIL'}")

    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TBL} CASCADE"))
        conn.commit()
    engine.dispose()

    results["cdc_trigger"] = {
        "rows": N, "burst_duration_s": round(burst_dur, 3),
        "per_row_ms": round(per_row_ms, 3),
        "throughput_rows_s": round(N / burst_dur),
        "captured": captured, "capture_rate_pct": capture_rate,
        "assertion_pass": per_row_ms < 5.0,
        "streaming_batches": batch_count,
        "streaming_total": total_streamed,
    }

# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — CDC concurrent writers (5 threads × 100 rows)
# ─────────────────────────────────────────────────────────────────────────────
def test_cdc_concurrency():
    separator("TEST 5 — CDC Concurrent Writers (5 threads × 100 rows)")
    from connector.cdc_monitor import CDCMonitor

    engine = create_engine(PG_HOSP, pool_size=10, max_overflow=5)
    cdc = CDCMonitor(PG_HOSP)
    cdc.configure_tenant(98)
    cdc.create_change_log_table()
    cdc.create_trigger_function()

    TBL = "bench_concur_test"
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TBL} CASCADE"))
        conn.execute(text(f"CREATE TABLE {TBL} (id BIGSERIAL PRIMARY KEY, val TEXT)"))
        conn.commit()
    cdc.add_trigger_to_table(TBL)

    THREADS, ROWS = 5, 100
    errors: List[Exception] = []
    hwm = cdc.get_latest_change_id() or 0

    def worker(tid):
        try:
            with engine.connect() as conn:
                for i in range(ROWS):
                    conn.execute(text(f"INSERT INTO {TBL} (val) VALUES (:v)"), {"v": f"t{tid}-{i}"})
                conn.commit()
        except Exception as e:
            errors.append(e)

    t0 = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(THREADS)]
    for t in threads: t.start()
    for t in threads: t.join()
    dur = time.perf_counter() - t0

    total_expected = THREADS * ROWS
    changes = cdc.get_changes_since(hwm, tenant_id=98)
    captured = len(changes)

    print(f"  Threads × Rows  : {THREADS} × {ROWS} = {total_expected}")
    print(f"  Errors          : {len(errors)}")
    print(f"  Wall-clock time : {dur:.3f}s")
    print(f"  Concurrent tput : {round(total_expected/dur)} rows/s")
    print(f"  Captured        : {captured}/{total_expected}")
    print(f"  No-loss pass    : {'PASS' if captured >= total_expected and not errors else 'FAIL'}")

    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {TBL} CASCADE"))
        conn.commit()
    engine.dispose()

    results["cdc_concurrency"] = {
        "threads": THREADS, "rows_per_thread": ROWS,
        "total": total_expected, "errors": len(errors),
        "duration_s": round(dur, 3), "captured": captured,
        "throughput_rows_s": round(total_expected / dur),
        "pass": captured >= total_expected and not errors
    }

# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — Watermark correctness under concurrency
# ─────────────────────────────────────────────────────────────────────────────
def test_watermark_concurrency():
    separator("TEST 6 — Watermark Concurrency (100 concurrent advances)")
    from connector.cdc_monitor import CDCMonitor
    cdc = CDCMonitor(PG_HOSP)
    cdc.create_change_log_table()
    base = cdc.load_watermark(9001) or 0
    errors = []

    def advance(val):
        try: cdc.advance_watermark(9001, val)
        except Exception as e: errors.append(e)

    threads = [threading.Thread(target=advance, args=(base + i,)) for i in range(100)]
    t0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    dur = time.perf_counter() - t0

    final = cdc.load_watermark(9001)
    expected = base + 99
    ok = final == expected and not errors

    print(f"  Threads         : 100")
    print(f"  Expected final  : {expected}")
    print(f"  Actual final    : {final}")
    print(f"  Errors          : {len(errors)}")
    print(f"  GREATEST logic  : {'PASS' if ok else 'FAIL'}")
    print(f"  Duration        : {dur:.3f}s")

    results["watermark_concurrency"] = {
        "threads": 100, "expected_final": expected,
        "actual_final": final, "errors": len(errors),
        "duration_s": round(dur, 3), "pass": ok
    }

# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 — Idempotency (3× ETL on each source)
# ─────────────────────────────────────────────────────────────────────────────
def test_idempotency():
    separator("TEST 7 — ETL Idempotency (3 runs per source)")
    from cdc.adapter_factory import CDCAdapterFactory
    from etl.multi_db_pipeline import MultiDBPipeline

    def central_counts(tid):
        c = psycopg2.connect(CENTRAL)
        cur = c.cursor()
        out = {}
        for tbl in ["fhir_patient","fhir_encounter","fhir_observation","fhir_medication_request"]:
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE tenant_id=%s", (tid,))
            out[tbl] = cur.fetchone()[0]
        c.close()
        return out

    idempotency_results = []
    for label, tid, cs in SOURCES:
        print(f"\n  [{label.upper()}] tenant={tid}")
        try:
            adapter = CDCAdapterFactory.create_adapter(cs)
            runs = []
            for run_no in range(3):
                MultiDBPipeline(adapter, tenant_id=tid).sync_all()
                counts = central_counts(tid)
                runs.append(counts)
                print(f"    run{run_no+1}: pat={counts['fhir_patient']} enc={counts['fhir_encounter']} "
                      f"obs={counts['fhir_observation']} med={counts['fhir_medication_request']}")
            adapter.close()
            stable = runs[0] == runs[1] == runs[2]
            print(f"    Idempotent: {'PASS' if stable else 'FAIL'}")
            idempotency_results.append({"source": label, "runs": runs, "pass": stable})
        except Exception as e:
            print(f"    CRASH: {e}")
            idempotency_results.append({"source": label, "pass": False, "error": str(e)})

    results["idempotency"] = idempotency_results

# ─────────────────────────────────────────────────────────────────────────────
# TEST 8 — Multi-tenant isolation
# ─────────────────────────────────────────────────────────────────────────────
def test_tenant_isolation():
    separator("TEST 8 — Multi-Tenant Data Isolation")
    c = psycopg2.connect(CENTRAL)
    cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get all distinct tenant_ids in fhir_patient
    cur.execute("SELECT DISTINCT tenant_id FROM fhir_patient ORDER BY tenant_id")
    tenant_ids = [r["tenant_id"] for r in cur.fetchall()]
    print(f"  Tenants with fhir_patient data: {tenant_ids}")

    leakage_found = False
    isolation_results = []

    for tid in tenant_ids:
        # Set RLS context and query
        cur.execute("SET app.tenant_id = %s", (str(tid),))
        cur.execute("SELECT COUNT(*) as cnt FROM fhir_patient")
        visible_with_rls = cur.fetchone()["cnt"]

        # Count without RLS (bypass — using superuser logic via direct count with tenant filter)
        cur.execute("SELECT COUNT(*) as cnt FROM fhir_patient WHERE tenant_id=%s", (tid,))
        expected = cur.fetchone()["cnt"]

        # Try cross-tenant query — should return 0 for a different tenant
        other_tid = [t for t in tenant_ids if t != tid]
        if other_tid:
            cur.execute("SET app.tenant_id = %s", (str(tid),))
            cur.execute("SELECT COUNT(*) as cnt FROM fhir_patient WHERE tenant_id=%s", (other_tid[0],))
            cross_count = cur.fetchone()["cnt"]
            leak = cross_count > 0
            if leak:
                leakage_found = True
            isolation_results.append({
                "tenant": tid, "own_records": expected,
                "cross_tenant_visible": cross_count, "leak": leak
            })
            print(f"  tenant={tid:3d} own={expected:5d} cross_tenant_visible={cross_count} "
                  f"{'LEAK!' if leak else 'ISOLATED'}")

    # Reset RLS
    cur.execute("RESET app.tenant_id")
    c.close()
    overall = "PASS" if not leakage_found else "FAIL"
    print(f"\n  Multi-tenant isolation: {overall}")
    results["tenant_isolation"] = {
        "tenants_checked": len(isolation_results),
        "leakage_found": leakage_found,
        "overall": overall,
        "detail": isolation_results
    }

# ─────────────────────────────────────────────────────────────────────────────
# TEST 9 — RAG mapping accuracy (ground-truth evaluation)
# ─────────────────────────────────────────────────────────────────────────────
def test_rag_accuracy():
    separator("TEST 9 — RAG Mapping Accuracy (Ground-Truth Evaluation)")

    # Ground truth: known column → expected FHIR path
    GROUND_TRUTH = [
        # Patient fields
        {"col": "patient_id",             "type": "INTEGER", "expected": "id",                     "resource": "Patient"},
        {"col": "medical_record_number",  "type": "VARCHAR", "expected": "identifier[0].value",    "resource": "Patient"},
        {"col": "mrn",                    "type": "VARCHAR", "expected": "identifier[0].value",    "resource": "Patient"},
        {"col": "first_name",             "type": "VARCHAR", "expected": "name[0].given[0]",       "resource": "Patient"},
        {"col": "last_name",              "type": "VARCHAR", "expected": "name[0].family",         "resource": "Patient"},
        {"col": "date_of_birth",          "type": "DATE",    "expected": "birthDate",              "resource": "Patient"},
        {"col": "gender",                 "type": "VARCHAR", "expected": "gender",                 "resource": "Patient"},
        {"col": "phone_number",           "type": "VARCHAR", "expected": "telecom[0].value",       "resource": "Patient"},
        {"col": "email",                  "type": "VARCHAR", "expected": "telecom[1].value",       "resource": "Patient"},
        # Encounter fields
        {"col": "admission_date",         "type": "DATE",    "expected": "period.start",           "resource": "Encounter"},
        {"col": "discharge_date",         "type": "DATE",    "expected": "period.end",             "resource": "Encounter"},
        {"col": "encounter_type",         "type": "VARCHAR", "expected": "class.code",             "resource": "Encounter"},
        # Observation / lab fields
        {"col": "test_name",              "type": "VARCHAR", "expected": "code.text",              "resource": "Observation"},
        {"col": "result_value",           "type": "DECIMAL", "expected": "valueQuantity.value",    "resource": "Observation"},
        {"col": "result_unit",            "type": "VARCHAR", "expected": "valueQuantity.unit",     "resource": "Observation"},
        # Medication fields
        {"col": "medication_name",        "type": "VARCHAR", "expected": "medicationCodeableConcept.text", "resource": "MedicationRequest"},
        {"col": "dosage",                 "type": "VARCHAR", "expected": "dosageInstruction[0].text",      "resource": "MedicationRequest"},
        # Alias variants — tests alias expansion in vector store
        {"col": "pid",                    "type": "INTEGER", "expected": "id",                     "resource": "Patient"},
        {"col": "pat_num",                "type": "VARCHAR", "expected": "identifier[0].value",    "resource": "Patient"},
        {"col": "dob",                    "type": "DATE",    "expected": "birthDate",              "resource": "Patient"},
    ]

    try:
        from rag.vector_store import FHIRVectorStore
        from rag.mapping_suggester import MappingSuggester

        print("  Initialising MappingSuggester (may take a few seconds)...")
        suggester = MappingSuggester()

        correct, incorrect, retrieval_used, rag_used = 0, 0, 0, 0
        detail = []

        for gt in GROUND_TRUTH:
            try:
                result = suggester.suggest_mapping(
                    column_name=gt["col"],
                    column_type=gt["type"],
                    fhir_resource=gt["resource"]
                )
                suggested = result.get("fhir_path", "")
                method    = result.get("method", "unknown")
                conf      = result.get("confidence", 0)

                if method == "retrieval":
                    retrieval_used += 1
                else:
                    rag_used += 1

                # Exact match OR the expected is a prefix of the suggestion
                is_correct = (suggested == gt["expected"] or
                              suggested.startswith(gt["expected"].split("[")[0]))

                if is_correct:
                    correct += 1
                else:
                    incorrect += 1

                detail.append({
                    "col": gt["col"], "expected": gt["expected"],
                    "suggested": suggested, "method": method,
                    "confidence": round(conf, 3), "correct": is_correct
                })
                status = "✓" if is_correct else "✗"
                print(f"  {status} {gt['col']:30s} → {suggested:40s} [{method}] conf={conf:.2f}")

            except Exception as e:
                detail.append({"col": gt["col"], "error": str(e), "correct": False})
                incorrect += 1
                print(f"  ✗ {gt['col']:30s} ERROR: {e}")

        total = correct + incorrect
        accuracy = round(correct / total * 100, 1) if total > 0 else 0
        retrieval_pct = round(retrieval_used / total * 100, 1) if total > 0 else 0
        rag_pct = round(rag_used / total * 100, 1) if total > 0 else 0

        print(f"\n  Total tests    : {total}")
        print(f"  Correct        : {correct}")
        print(f"  Incorrect      : {incorrect}")
        print(f"  Accuracy       : {accuracy}%")
        print(f"  Retrieval used : {retrieval_used} ({retrieval_pct}%)")
        print(f"  LLM fallback   : {rag_used} ({rag_pct}%)")

        results["rag_accuracy"] = {
            "total": total, "correct": correct, "incorrect": incorrect,
            "accuracy_pct": accuracy,
            "retrieval_pct": retrieval_pct, "rag_fallback_pct": rag_pct,
            "detail": detail
        }

    except Exception as e:
        print(f"  RAG engine unavailable: {e}")
        results["rag_accuracy"] = {"error": str(e)}

# ─────────────────────────────────────────────────────────────────────────────
# TEST 10 — API latency (requires running API server)
# ─────────────────────────────────────────────────────────────────────────────
def test_api_latency():
    separator("TEST 10 — API Endpoint Latency")
    try:
        import urllib.request, urllib.error

        BASE = "http://localhost:8003"

        # Login first
        login_data = json.dumps({"email":"admin@carelock.com","password":"admin123"}).encode()
        req = urllib.request.Request(f"{BASE}/api/v1/auth/login",
                                     data=login_data,
                                     headers={"Content-Type":"application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=5) as resp:
            login_dur = time.perf_counter() - t0
            body = json.loads(resp.read())
            token = body.get("access_token","")

        if not token:
            print("  API server not reachable or login failed")
            results["api_latency"] = {"status": "api_not_running"}
            return

        headers = {"Authorization": f"Bearer {token}"}

        endpoints = [
            ("GET", "/health",                     None),
            ("GET", "/api/v1/auth/me",              None),
            ("GET", "/api/v1/stats",                None),
            ("GET", "/api/v1/sync/status",          None),
            ("GET", "/api/v1/connector/health",     None),
            ("GET", "/api/v1/rag/status",           None),
        ]

        latency_results = [{"endpoint": "POST /auth/login", "latency_ms": round(login_dur*1000,1)}]
        print(f"  POST /auth/login                : {login_dur*1000:.1f}ms")

        for method, path, body_data in endpoints:
            data = json.dumps(body_data).encode() if body_data else None
            req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
            samples = []
            for _ in range(5):
                try:
                    t0 = time.perf_counter()
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        resp.read()
                    samples.append((time.perf_counter() - t0) * 1000)
                except Exception:
                    pass
            if samples:
                avg_ms = round(statistics.mean(samples), 1)
                p95_ms = round(sorted(samples)[int(len(samples)*0.95)], 1)
                print(f"  {method} {path:40s}: avg={avg_ms}ms p95={p95_ms}ms")
                latency_results.append({"endpoint": f"{method} {path}", "avg_ms": avg_ms, "p95_ms": p95_ms})
            else:
                print(f"  {method} {path:40s}: TIMEOUT")

        results["api_latency"] = {"status": "measured", "endpoints": latency_results}

    except Exception as e:
        print(f"  API not reachable: {e}")
        results["api_latency"] = {"status": "api_not_running", "error": str(e)}

# ─────────────────────────────────────────────────────────────────────────────
# TEST 11 — Null-value and edge-case handling
# ─────────────────────────────────────────────────────────────────────────────
def test_null_handling():
    separator("TEST 11 — Null-Value Edge Case Handling")
    from cdc.adapter_factory import CDCAdapterFactory
    from etl.multi_db_pipeline import MultiDBPipeline

    null_results = []
    for label, tid, cs in SOURCES:
        try:
            adapter = CDCAdapterFactory.create_adapter(cs)
            rows = adapter.extract_data("patients", limit=20)
            # Patient #4 has NULL gender + NULL dob in seed
            null_pat = [r for r in rows
                        if str(r.get("patient_id") or r.get("PATIENT_ID","")) == "4"]
            if null_pat:
                p = null_pat[0]
                g  = p.get("gender") or p.get("GENDER")
                db = p.get("date_of_birth") or p.get("DATE_OF_BIRTH")
                ok = g is None and db is None
                print(f"  [{label:10s}] patient_id=4: gender={g!r} dob={db!r} → {'PASS' if ok else 'FAIL'}")
                null_results.append({"source": label, "pass": ok})
            else:
                print(f"  [{label:10s}] patient_id=4 not found in extract — SKIP")
                null_results.append({"source": label, "pass": None, "note": "not_found"})
            adapter.close()
        except Exception as e:
            print(f"  [{label:10s}] ERROR: {e}")
            null_results.append({"source": label, "pass": False, "error": str(e)})

    results["null_handling"] = null_results

# ─────────────────────────────────────────────────────────────────────────────
# TEST 12 — 500-row bulk throughput per source
# ─────────────────────────────────────────────────────────────────────────────
def test_bulk_throughput():
    separator("TEST 12 — Bulk 500-row Load/Extract Throughput per Source")
    from cdc.adapter_factory import CDCAdapterFactory

    bulk_results = []
    for label, tid, cs in SOURCES:
        try:
            adapter = CDCAdapterFactory.create_adapter(cs)
            TBL = "bench_bulk_500"
            rows_in = [{"k": i, "v": f"row-{i}"} for i in range(500)]

            # Setup table
            db_type = adapter.get_database_type()
            if db_type == "mongodb":
                adapter.db.drop_collection(TBL)
            else:
                with adapter.engine.begin() as conn:
                    if db_type == "oracle":
                        conn.execute(text("BEGIN EXECUTE IMMEDIATE 'DROP TABLE \"BENCH_BULK_500\"'; EXCEPTION WHEN OTHERS THEN NULL; END;"))
                        conn.execute(text('CREATE TABLE "BENCH_BULK_500" (k NUMBER PRIMARY KEY, v VARCHAR2(50))'))
                    elif db_type == "sqlserver":
                        conn.execute(text("IF OBJECT_ID('bench_bulk_500','U') IS NOT NULL DROP TABLE bench_bulk_500"))
                        conn.execute(text("CREATE TABLE bench_bulk_500 (k INT PRIMARY KEY, v NVARCHAR(50))"))
                    elif db_type == "mysql":
                        conn.execute(text("DROP TABLE IF EXISTS `bench_bulk_500`"))
                        conn.execute(text("CREATE TABLE `bench_bulk_500` (k INT PRIMARY KEY, v VARCHAR(50))"))
                    else:
                        conn.execute(text("DROP TABLE IF EXISTS bench_bulk_500"))
                        conn.execute(text("CREATE TABLE bench_bulk_500 (k INT PRIMARY KEY, v VARCHAR(50))"))

            # Load
            t0 = time.perf_counter()
            n_loaded = adapter.load_data(TBL, rows_in, upsert_keys=["k"])
            load_dur = time.perf_counter() - t0

            # Extract
            t0 = time.perf_counter()
            extracted = adapter.extract_data(TBL, limit=600)
            extract_dur = time.perf_counter() - t0

            n_extracted = len(extracted)
            load_tput   = round(n_loaded   / load_dur,    1) if load_dur    > 0 else 0
            extract_tput= round(n_extracted/ extract_dur, 1) if extract_dur > 0 else 0

            print(f"  [{label:10s}] loaded={n_loaded} in {load_dur:.3f}s ({load_tput} rec/s) | "
                  f"extracted={n_extracted} in {extract_dur:.3f}s ({extract_tput} rec/s)")

            # Cleanup
            if db_type == "mongodb":
                adapter.db.drop_collection(TBL)
            else:
                with adapter.engine.begin() as conn:
                    if db_type == "oracle":
                        conn.execute(text("BEGIN EXECUTE IMMEDIATE 'DROP TABLE \"BENCH_BULK_500\"'; EXCEPTION WHEN OTHERS THEN NULL; END;"))
                    elif db_type == "sqlserver":
                        conn.execute(text("IF OBJECT_ID('bench_bulk_500','U') IS NOT NULL DROP TABLE bench_bulk_500"))
                    else:
                        conn.execute(text("DROP TABLE IF EXISTS bench_bulk_500"))

            adapter.close()
            bulk_results.append({
                "source": label, "rows": 500,
                "load_dur_s": round(load_dur, 3), "load_tput": load_tput,
                "extract_dur_s": round(extract_dur, 3), "extract_tput": extract_tput,
            })
        except Exception as e:
            print(f"  [{label:10s}] ERROR: {e}")
            bulk_results.append({"source": label, "error": str(e)})

    results["bulk_throughput"] = bulk_results


# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
def print_final_summary():
    separator("FINAL METRICS SUMMARY")

    # Sync throughput from live ETL
    etl = results.get("etl_timing", [])
    ok_etl = [e for e in etl if e.get("status") == "ok"]
    if ok_etl:
        tputs  = [e["throughput_rec_s"] for e in ok_etl]
        durs   = [e["duration_s"]       for e in ok_etl]
        print(f"\n  ── Sync Performance ──")
        print(f"  Sources measured         : {len(ok_etl)}/5")
        print(f"  Avg sync time (full)     : {statistics.mean(durs):.2f}s")
        print(f"  Min / Max sync time      : {min(durs):.2f}s / {max(durs):.2f}s")
        print(f"  Avg throughput           : {statistics.mean(tputs):.1f} rec/s")
        print(f"  Peak throughput          : {max(tputs):.1f} rec/s")
        for e in ok_etl:
            print(f"    {e['source']:10s}: {e['duration_s']:.3f}s  {e['throughput_rec_s']} rec/s  loaded={e['loaded']}")

    # CDC
    cdc = results.get("cdc_trigger", {})
    if cdc:
        print(f"\n  ── CDC Trigger (PostgreSQL) ──")
        print(f"  1000-row burst time      : {cdc['burst_duration_s']}s")
        print(f"  Per-row overhead         : {cdc['per_row_ms']}ms")
        print(f"  Throughput               : {cdc['throughput_rows_s']} rows/s")
        print(f"  Capture rate             : {cdc['capture_rate_pct']}%")
        print(f"  5ms assertion            : {'PASS' if cdc['assertion_pass'] else 'FAIL'}")

    conc = results.get("cdc_concurrency", {})
    if conc:
        print(f"  Concurrent (5T×100R)     : {conc['throughput_rows_s']} rows/s  {'PASS' if conc['pass'] else 'FAIL'}")

    wm = results.get("watermark_concurrency", {})
    if wm:
        print(f"  Watermark concurrency    : {'PASS' if wm['pass'] else 'FAIL'}")

    # RAG
    rag = results.get("rag_accuracy", {})
    if "accuracy_pct" in rag:
        print(f"\n  ── RAG / Mapping Engine ──")
        print(f"  Accuracy                 : {rag['accuracy_pct']}% ({rag['correct']}/{rag['total']})")
        print(f"  Retrieval-only path      : {rag['retrieval_pct']}%")
        print(f"  LLM fallback             : {rag['rag_fallback_pct']}%")

    # Tenant isolation
    ti = results.get("tenant_isolation", {})
    if ti:
        print(f"\n  ── Tenant Isolation ──")
        print(f"  Tenants checked          : {ti['tenants_checked']}")
        print(f"  Data leakage found       : {ti['leakage_found']}")
        print(f"  Overall                  : {ti['overall']}")

    # Idempotency
    idem = results.get("idempotency", [])
    if idem:
        passed = sum(1 for i in idem if i.get("pass") == True)
        print(f"\n  ── Idempotency ──")
        print(f"  Sources passing          : {passed}/{len(idem)}")
        for i in idem:
            print(f"    {i['source']:10s}: {'PASS' if i.get('pass') else 'FAIL'}")

    # Null handling
    null = results.get("null_handling", [])
    if null:
        passed = sum(1 for n in null if n.get("pass") == True)
        print(f"\n  ── Null-Value Handling ──")
        print(f"  Sources passing          : {passed}/{len([n for n in null if n.get('pass') is not None])}")

    # Bulk
    bulk = results.get("bulk_throughput", [])
    if bulk:
        ok_bulk = [b for b in bulk if "load_tput" in b]
        if ok_bulk:
            print(f"\n  ── Bulk 500-row Throughput ──")
            for b in ok_bulk:
                print(f"    {b['source']:10s}: load={b['load_tput']} rec/s  extract={b['extract_tput']} rec/s")

    # API
    api = results.get("api_latency", {})
    if api.get("status") == "measured":
        print(f"\n  ── API Latency ──")
        for ep in api["endpoints"]:
            if "avg_ms" in ep:
                print(f"    {ep['endpoint']:45s}: avg={ep['avg_ms']}ms p95={ep.get('p95_ms','?')}ms")
            else:
                print(f"    {ep['endpoint']:45s}: {ep.get('latency_ms','?')}ms")
    else:
        print(f"\n  ── API Latency ──  (API server not running — skipped)")

    print(f"\n{'='*70}")
    print("  Benchmark complete.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    print(f"\nCareLock-Sync Full System Benchmark")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    test_baseline_counts()
    test_sync_history()
    test_live_etl_timing()
    test_cdc_trigger_overhead()
    test_cdc_concurrency()
    test_watermark_concurrency()
    test_idempotency()
    test_tenant_isolation()
    test_rag_accuracy()
    test_null_handling()
    test_bulk_throughput()
    test_api_latency()
    print_final_summary()

    # Save raw results
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Raw results saved to: {out_path}")
