#!/usr/bin/env python3
"""
verify_multi_db_etl.py — runs MultiDBPipeline against every source DB
and prints per-resource extracted/transformed/loaded counts.

Each source uses its own tenant_id so loaded rows can be inspected
separately in the central FHIR DB.
"""
from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from cdc.adapter_factory import CDCAdapterFactory
from etl.multi_db_pipeline import MultiDBPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("etl-verify")

CONNS = [
    ("postgres",  10, "postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db"),
    ("mysql",     11, "mysql://hospital_user:hospital_pass@localhost:3306/hospital_db_mysql"),
    ("mongodb",   12, "mongodb://localhost:27017/hospital_db_mongodb"),
    ("oracle",    13, "oracle://hospital_user:hospital_pass@localhost:1521/XEPDB1"),
    ("sqlserver", 14, "sqlserver://sa:YourStrong@Passw0rd@localhost:1433/hospital_db_sqlserver"),
]

CENTRAL = "postgresql://shared_user:shared_pass@localhost:5433/carelock_shared"


def _ensure_tenants():
    """Make sure synthetic tenant_ids exist in hospital_tenants."""
    e = create_engine(CENTRAL)
    with e.begin() as c:
        for label, tid, _ in CONNS:
            c.execute(text("""
                INSERT INTO hospital_tenants (tenant_id, hospital_name, hospital_code, is_active)
                VALUES (:tid, :name, :code, TRUE)
                ON CONFLICT (tenant_id) DO NOTHING
            """), {
                "tid": tid,
                "name": f"DEMO {label.upper()} Hospital",
                "code": f"DEMO{label.upper()[:3]}",
            })
    e.dispose()


def _count_central(tenant_id: int) -> dict:
    e = create_engine(CENTRAL)
    out = {}
    with e.connect() as c:
        for tbl in ("fhir_patient", "fhir_encounter",
                    "fhir_observation", "fhir_medication_request"):
            try:
                out[tbl] = c.execute(
                    text(f"SELECT COUNT(*) FROM {tbl} WHERE tenant_id = :t"),
                    {"t": tenant_id},
                ).scalar()
            except Exception:
                out[tbl] = "?"
    e.dispose()
    return out


def main() -> int:
    _ensure_tenants()
    print("\n" + "=" * 78)
    print(" Multi-DB ETL Pipeline Verification")
    print("=" * 78)

    failures = 0
    summary = []

    for label, tid, cs in CONNS:
        print(f"\n  ──── {label.upper()}  tenant={tid}  ────")
        try:
            adapter = CDCAdapterFactory.create_adapter(cs)
            if not adapter.validate_connection():
                print(f"    [FAIL] cannot connect to {label}")
                failures += 1
                summary.append((label, "DOWN", {}))
                continue

            pipe = MultiDBPipeline(adapter, tenant_id=tid)
            stats = pipe.sync_all(limit=20)
            adapter.close()

            for resource, s in stats.items():
                print(f"    {resource:14s}  extracted={s['extracted']:3d}  "
                      f"transformed={s['transformed']:3d}  "
                      f"loaded={s['loaded']:3d}  "
                      f"errors={s['errors']}")

            central = _count_central(tid)
            print("    central FHIR rows:")
            for tbl, n in central.items():
                print(f"      {tbl:30s} = {n}")
            summary.append((label, "OK", stats))
        except Exception as exc:
            log.error("%s pipeline crashed: %s", label, exc)
            failures += 1
            summary.append((label, "CRASH", {}))

    print("\n" + "=" * 78)
    print(" SUMMARY")
    print("=" * 78)
    for label, status, stats in summary:
        if status == "OK":
            total = sum(s["loaded"] for s in stats.values())
            errs = sum(s["errors"] for s in stats.values())
            print(f"  [{status:5s}]  {label:10s}  loaded={total}  errors={errs}")
        else:
            print(f"  [{status:5s}]  {label}")
    print(f"  {len(CONNS) - failures}/{len(CONNS)} sources completed without crash")
    return failures


if __name__ == "__main__":
    sys.exit(main())
