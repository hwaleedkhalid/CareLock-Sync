#!/usr/bin/env python3
"""
verify_load_data.py — exercises ``adapter.load_data`` on every source,
then reads back to confirm rows are actually persisted.

For each DB:
  1. Insert one synthetic row into ``patients`` with a sentinel mrn
  2. Read back via ``extract_data`` and check the row is present
  3. Issue an upsert that updates ``first_name`` and re-verify
  4. Clean up the sentinel row

Exits 0 only when all 5 sources round-trip cleanly.
"""
from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from sqlalchemy import text
from cdc.adapter_factory import CDCAdapterFactory

CONNS = [
    ("postgres ", "postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db"),
    ("mysql    ", "mysql://hospital_user:hospital_pass@localhost:3306/hospital_db_mysql"),
    ("mongodb  ", "mongodb://localhost:27017/hospital_db_mongodb"),
    ("oracle   ", "oracle://hospital_user:hospital_pass@localhost:1521/XEPDB1"),
    ("sqlserver", "sqlserver://sa:YourStrong@Passw0rd@localhost:1433/hospital_db_sqlserver"),
]

SENTINEL_PID = 9999
SENTINEL_MRN = "MRN-SENTINEL"


def _row():
    return {
        "patient_id":    SENTINEL_PID,
        "mrn":           SENTINEL_MRN,
        "first_name":    "TestUser",
        "last_name":     "Loaded",
        "date_of_birth": date(1990, 6, 15),
        "gender":        "M",
    }


def _cleanup(adapter, dbtype: str):
    """Best-effort delete of the sentinel row."""
    try:
        if dbtype == "mongodb":
            adapter.db["patients"].delete_one({"patient_id": SENTINEL_PID})
        else:
            with adapter.engine.begin() as c:
                tbl = "patients"
                if dbtype == "oracle":
                    c.execute(text(f'DELETE FROM "PATIENTS" WHERE PATIENT_ID = :p'),
                              {"p": SENTINEL_PID})
                else:
                    c.execute(text(f"DELETE FROM patients WHERE patient_id = :p"),
                              {"p": SENTINEL_PID})
    except Exception:
        pass


def verify(label: str, cs: str) -> bool:
    print(f"\n  [{label}]  {cs.split('://')[0]}")
    a = CDCAdapterFactory.create_adapter(cs)
    dbtype = a.get_database_type()
    if not a.validate_connection():
        print("    [FAIL] cannot connect"); return False

    _cleanup(a, dbtype)

    # 1. Insert
    try:
        n = a.load_data("patients", [_row()], upsert_keys=["patient_id"])
        print(f"    [OK]   load_data() insert -> {n} rows written")
    except Exception as e:
        print(f"    [FAIL] load_data insert: {e}"); _cleanup(a, dbtype); return False

    # 2. Read back
    try:
        rows = a.extract_data("patients", limit=1000)
        match = [r for r in rows if r.get("patient_id") == SENTINEL_PID
                  or r.get("PATIENT_ID") == SENTINEL_PID]
        if not match:
            print("    [FAIL] row not found after insert"); _cleanup(a, dbtype); return False
        rec = match[0]
        # Allow either case
        fn = rec.get("first_name") or rec.get("FIRST_NAME")
        print(f"    [OK]   read-back: patient_id={SENTINEL_PID}  first_name={fn!r}")
    except Exception as e:
        print(f"    [FAIL] read-back: {e}"); _cleanup(a, dbtype); return False

    # 3. Upsert update
    try:
        upd = _row(); upd["first_name"] = "Updated"
        a.load_data("patients", [upd], upsert_keys=["patient_id"])
        rows = a.extract_data("patients", limit=1000)
        match = [r for r in rows if r.get("patient_id") == SENTINEL_PID
                  or r.get("PATIENT_ID") == SENTINEL_PID]
        fn = match[0].get("first_name") or match[0].get("FIRST_NAME")
        if fn != "Updated":
            print(f"    [FAIL] upsert update did not stick (got {fn!r})")
            _cleanup(a, dbtype); return False
        print(f"    [OK]   upsert update -> first_name={fn!r}")
    except Exception as e:
        print(f"    [FAIL] upsert update: {e}"); _cleanup(a, dbtype); return False

    # 4. Cleanup
    _cleanup(a, dbtype)
    a.close()
    return True


def main() -> int:
    print("=" * 70)
    print(" load_data round-trip verification")
    print("=" * 70)
    fail = 0
    for label, cs in CONNS:
        try:
            ok = verify(label, cs)
            if not ok: fail += 1
        except Exception as e:
            print(f"    [CRASH] {e}")
            fail += 1
    print("\n" + "=" * 70)
    print(f"  Result: {len(CONNS) - fail}/{len(CONNS)} sources passed")
    print("=" * 70)
    return fail


if __name__ == "__main__":
    sys.exit(main())
