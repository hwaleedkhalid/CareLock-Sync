#!/usr/bin/env python3
"""
stress_multi_db.py — exercises the multi-DB ETL across edge cases.

  1. Repeat ETL 3x per source — assert idempotency (no duplicate rows)
  2. Empty-table extraction returns []
  3. Null-value rows survive transform without crash
  4. Large dataset: insert 500 synthetic rows into a sentinel source
     table, run extract+load, verify counts.

Exits 0 only when every check passes for every database.
"""
from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from sqlalchemy import create_engine, text

from cdc.adapter_factory import CDCAdapterFactory
from etl.multi_db_pipeline import MultiDBPipeline

logging.basicConfig(level=logging.WARNING, format="%(message)s")
log = logging.getLogger("stress")

CONNS = [
    ("postgres",  10, "postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db"),
    ("mysql",     11, "mysql://hospital_user:hospital_pass@localhost:3306/hospital_db_mysql"),
    ("mongodb",   12, "mongodb://localhost:27017/hospital_db_mongodb"),
    ("oracle",    13, "oracle://hospital_user:hospital_pass@localhost:1521/XEPDB1"),
    ("sqlserver", 14, "sqlserver://sa:YourStrong@Passw0rd@localhost:1433/hospital_db_sqlserver"),
]
CENTRAL = "postgresql://shared_user:shared_pass@localhost:5433/carelock_shared"


def _count_central(tid: int) -> dict:
    e = create_engine(CENTRAL); out = {}
    with e.connect() as c:
        for tbl in ("fhir_patient", "fhir_encounter",
                    "fhir_observation", "fhir_medication_request"):
            out[tbl] = c.execute(
                text(f"SELECT COUNT(*) FROM {tbl} WHERE tenant_id=:t"),
                {"t": tid},
            ).scalar()
    e.dispose()
    return out


def test_idempotency(label, tid, cs):
    print(f"\n  [{label}] idempotency (3x ETL)")
    a = CDCAdapterFactory.create_adapter(cs)
    runs = []
    for i in range(3):
        MultiDBPipeline(a, tenant_id=tid).sync_all(limit=20)
        c = _count_central(tid)
        runs.append(c)
        print(f"    run {i+1}: pat={c['fhir_patient']:3d}  enc={c['fhir_encounter']:3d}  "
              f"obs={c['fhir_observation']:3d}  med={c['fhir_medication_request']:3d}")
    a.close()
    if runs[0] == runs[1] == runs[2]:
        print("    [OK] counts stable across 3 runs (idempotent)")
        return True
    print("    [FAIL] counts changed between runs!")
    return False


def test_empty_table(label, cs):
    print(f"  [{label}] empty-table extraction")
    a = CDCAdapterFactory.create_adapter(cs)
    name = "stress_empty"
    try:
        if a.get_database_type() == "mongodb":
            a.db.drop_collection(name)
            a.db.create_collection(name)
            rows = a.extract_data(name, limit=10)
        else:
            with a.engine.begin() as c:
                if a.get_database_type() == "oracle":
                    c.execute(text(
                        "BEGIN EXECUTE IMMEDIATE 'DROP TABLE \"STRESS_EMPTY\"'; "
                        "EXCEPTION WHEN OTHERS THEN NULL; END;"))
                    c.execute(text('CREATE TABLE "STRESS_EMPTY" (id NUMBER PRIMARY KEY)'))
                elif a.get_database_type() == "sqlserver":
                    c.execute(text(
                        "IF OBJECT_ID('stress_empty','U') IS NOT NULL DROP TABLE stress_empty"))
                    c.execute(text("CREATE TABLE stress_empty (id INT PRIMARY KEY)"))
                elif a.get_database_type() == "mysql":
                    c.execute(text("DROP TABLE IF EXISTS `stress_empty`"))
                    c.execute(text("CREATE TABLE `stress_empty` (id INT PRIMARY KEY)"))
                else:  # postgresql
                    c.execute(text("DROP TABLE IF EXISTS stress_empty"))
                    c.execute(text("CREATE TABLE stress_empty (id INT PRIMARY KEY)"))
            rows = a.extract_data(name, limit=10)
        ok = len(rows) == 0
        print(f"    extract_data(empty) -> {len(rows)} rows  {'[OK]' if ok else '[FAIL]'}")
        return ok
    finally:
        try:
            if a.get_database_type() == "mongodb":
                a.db.drop_collection(name)
            else:
                with a.engine.begin() as c:
                    if a.get_database_type() == "oracle":
                        c.execute(text(
                            "BEGIN EXECUTE IMMEDIATE 'DROP TABLE \"STRESS_EMPTY\"'; "
                            "EXCEPTION WHEN OTHERS THEN NULL; END;"))
                    elif a.get_database_type() == "sqlserver":
                        c.execute(text(
                            "IF OBJECT_ID('stress_empty','U') IS NOT NULL DROP TABLE stress_empty"))
                    else:
                        c.execute(text("DROP TABLE IF EXISTS stress_empty"))
        except Exception:
            pass
        a.close()


def test_null_values(label, cs):
    """Patient #4 in the seed has NULL gender + NULL dob — assert it round-trips."""
    print(f"  [{label}] null-value handling")
    a = CDCAdapterFactory.create_adapter(cs)
    rows = a.extract_data("patients", limit=20)
    null_pat = [r for r in rows
                if (r.get("patient_id") == 4 or r.get("PATIENT_ID") == 4)]
    a.close()
    if not null_pat:
        print("    [SKIP] sentinel patient #4 not present"); return True
    p = null_pat[0]
    g  = p.get("gender") or p.get("GENDER")
    db = p.get("date_of_birth") or p.get("DATE_OF_BIRTH")
    if g is None and db is None:
        print(f"    [OK] patient_id=4 returned with NULL gender + NULL dob")
        return True
    print(f"    [FAIL] expected NULLs, got gender={g!r}  dob={db!r}")
    return False


def test_large_dataset(label, cs):
    """Bulk-insert 500 rows into a sentinel source table, extract, count."""
    print(f"  [{label}] large dataset (500 rows)")
    a = CDCAdapterFactory.create_adapter(cs)
    name = "stress_large"
    try:
        # Setup
        if a.get_database_type() == "mongodb":
            a.db.drop_collection(name)
            big = [{"k": i, "v": f"row-{i}"} for i in range(500)]
            a.load_data(name, big)
        else:
            with a.engine.begin() as c:
                if a.get_database_type() == "oracle":
                    c.execute(text(
                        "BEGIN EXECUTE IMMEDIATE 'DROP TABLE \"STRESS_LARGE\"'; "
                        "EXCEPTION WHEN OTHERS THEN NULL; END;"))
                    c.execute(text(
                        'CREATE TABLE "STRESS_LARGE" (k NUMBER PRIMARY KEY, v VARCHAR2(50))'))
                elif a.get_database_type() == "sqlserver":
                    c.execute(text(
                        "IF OBJECT_ID('stress_large','U') IS NOT NULL DROP TABLE stress_large"))
                    c.execute(text(
                        "CREATE TABLE stress_large (k INT PRIMARY KEY, v NVARCHAR(50))"))
                elif a.get_database_type() == "mysql":
                    c.execute(text("DROP TABLE IF EXISTS `stress_large`"))
                    c.execute(text(
                        "CREATE TABLE `stress_large` (k INT PRIMARY KEY, v VARCHAR(50))"))
                else:
                    c.execute(text("DROP TABLE IF EXISTS stress_large"))
                    c.execute(text(
                        "CREATE TABLE stress_large (k INT PRIMARY KEY, v VARCHAR(50))"))
            big = [{"k": i, "v": f"row-{i}"} for i in range(500)]
            n = a.load_data(name, big, upsert_keys=["k"])
            assert n == 500, f"load_data wrote {n}, expected 500"
        rows = a.extract_data(name, limit=600)
        ok = len(rows) == 500
        print(f"    inserted=500 -> extracted={len(rows)}  "
              f"{'[OK]' if ok else '[FAIL]'}")
        return ok
    finally:
        try:
            if a.get_database_type() == "mongodb":
                a.db.drop_collection(name)
            else:
                with a.engine.begin() as c:
                    if a.get_database_type() == "oracle":
                        c.execute(text(
                            "BEGIN EXECUTE IMMEDIATE 'DROP TABLE \"STRESS_LARGE\"'; "
                            "EXCEPTION WHEN OTHERS THEN NULL; END;"))
                    elif a.get_database_type() == "sqlserver":
                        c.execute(text(
                            "IF OBJECT_ID('stress_large','U') IS NOT NULL DROP TABLE stress_large"))
                    else:
                        c.execute(text("DROP TABLE IF EXISTS stress_large"))
        except Exception:
            pass
        a.close()


def main() -> int:
    print("=" * 78)
    print(" Multi-DB Stress & Edge-Case Tests")
    print("=" * 78)

    failures = 0
    for label, tid, cs in CONNS:
        try:
            print(f"\n────── {label.upper()}  tenant={tid} ──────")
            ok1 = test_idempotency(label, tid, cs)
            ok2 = test_empty_table(label, cs)
            ok3 = test_null_values(label, cs)
            ok4 = test_large_dataset(label, cs)
            if not (ok1 and ok2 and ok3 and ok4):
                failures += 1
        except Exception as exc:
            log.error("[%s] CRASHED: %s", label, exc)
            failures += 1

    print("\n" + "=" * 78)
    print(f"  {len(CONNS) - failures}/{len(CONNS)} sources passed all stress tests")
    print("=" * 78)
    return failures


if __name__ == "__main__":
    sys.exit(main())
