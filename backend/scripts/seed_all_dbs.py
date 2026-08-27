#!/usr/bin/env python3
"""
seed_all_dbs.py — populate every source DB with a uniform minimal
clinical dataset so the multi-DB ETL pipeline can be verified
end-to-end on identical inputs.

Schema (per DB):
    patients     (patient_id PK, mrn, first_name, last_name, dob, gender)
    encounters   (encounter_id PK, patient_id FK, type, status,
                  start_date, end_date)
    lab_results  (lab_result_id PK, patient_id, encounter_id, test_name,
                  test_value, test_unit, status, observed_at)
    medications  (medication_id PK, patient_id, encounter_id, name,
                  dose, frequency, route, status, prescribed_at)

For MongoDB the same field names are used as document keys; ``_id`` is
auto-generated.

Re-runnable: existing rows are upserted (or skipped on PK conflict).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, date, timedelta
from typing import Any, Dict, List

_THIS = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_THIS)
sys.path.insert(0, _BACKEND)

from sqlalchemy import create_engine, text       # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("seed")


# ─────────────────────────────────────────────────────────────────────────────
# Demo dataset (10 patients, 20 encounters, 30 lab results, 15 medications)
# Includes deliberate edge cases:
#   * patient #4 has NULL gender + NULL dob
#   * patient #7 has empty last_name
#   * medication #3 has NULL frequency
# ─────────────────────────────────────────────────────────────────────────────
_BASE = date(2025, 1, 1)


def _patients() -> List[Dict[str, Any]]:
    rows = []
    for i in range(1, 11):
        rows.append({
            "patient_id": i,
            "mrn":        f"MRN-{1000+i:04d}",
            "first_name": ["Ali", "Bilal", "Cara", "Dina", "Erum",
                           "Faiz", "Gul", "Hira", "Imad", "Junaid"][i-1],
            "last_name":  None if i == 7 else ["Khan","Ahmed","Iqbal","Sheikh","Malik",
                           "Raza","Aslam","Tariq","Saeed","Waris"][i-1],
            "date_of_birth": None if i == 4 else (_BASE.replace(year=1960+i) ),
            "gender":     None if i == 4 else ("F" if i % 2 == 0 else "M"),
        })
    return rows


def _encounters() -> List[Dict[str, Any]]:
    rows = []
    eid = 100
    for pid in range(1, 11):
        for j in range(2):
            eid += 1
            rows.append({
                "encounter_id": eid,
                "patient_id":   pid,
                "encounter_type": "outpatient" if j == 0 else "inpatient",
                "status":       "finished",
                "start_date":   _BASE + timedelta(days=eid),
                "end_date":     _BASE + timedelta(days=eid+1),
            })
    return rows


def _lab_results() -> List[Dict[str, Any]]:
    rows = []
    lid = 200
    for pid in range(1, 11):
        for k, (name, val, unit) in enumerate([
            ("Hemoglobin", 13.5, "g/dL"),
            ("Glucose",    98.0, "mg/dL"),
            ("WBC",         7.2, "x10^9/L"),
        ]):
            lid += 1
            rows.append({
                "lab_result_id":  lid,
                "patient_id":     pid,
                "encounter_id":   100 + (pid * 2),
                "test_name":      name,
                "test_value":     val + pid * 0.1,
                "test_unit":      unit,
                "status":         "final",
                "observed_at":    datetime.combine(_BASE + timedelta(days=lid),
                                                   datetime.min.time()),
            })
    return rows


def _medications() -> List[Dict[str, Any]]:
    rows = []
    mid = 300
    for pid in range(1, 11):
        if pid > 5:  # only half the patients get meds
            continue
        for k, (name, dose, freq, route) in enumerate([
            ("Paracetamol", "500mg", "TID", "PO"),
            ("Amoxicillin", "250mg", None if pid == 3 else "BID", "PO"),
            ("Insulin",     "10IU",  "QID", "SC"),
        ]):
            mid += 1
            rows.append({
                "medication_id":  mid,
                "patient_id":     pid,
                "encounter_id":   100 + (pid * 2),
                "name":           name,
                "dose":           dose,
                "frequency":      freq,
                "route":          route,
                "status":         "active",
                "prescribed_at":  datetime.combine(_BASE + timedelta(days=mid),
                                                   datetime.min.time()),
            })
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Per-DB seed implementations
# ─────────────────────────────────────────────────────────────────────────────
def _seed_postgres(cs: str) -> None:
    log.info("[postgres] connecting %s", _redact(cs))
    e = create_engine(cs, pool_pre_ping=True)
    with e.begin() as c:
        # legacy schemas from earlier sprints carry incompatible columns;
        # drop & recreate for a clean, demo-stable schema
        for t in ("medications", "lab_results", "encounters", "patients"):
            c.execute(text(f"DROP TABLE IF EXISTS {t} CASCADE"))
        c.execute(text("""
            CREATE TABLE patients (
                patient_id INT PRIMARY KEY,
                mrn VARCHAR(20) UNIQUE,
                first_name VARCHAR(50), last_name VARCHAR(50),
                date_of_birth DATE, gender CHAR(1)
            )"""))
        c.execute(text("""
            CREATE TABLE encounters (
                encounter_id INT PRIMARY KEY,
                patient_id INT REFERENCES patients(patient_id),
                encounter_type VARCHAR(20), status VARCHAR(20),
                start_date DATE, end_date DATE
            )"""))
        c.execute(text("""
            CREATE TABLE lab_results (
                lab_result_id INT PRIMARY KEY,
                patient_id INT, encounter_id INT,
                test_name VARCHAR(50), test_value NUMERIC, test_unit VARCHAR(20),
                status VARCHAR(20), observed_at TIMESTAMP
            )"""))
        c.execute(text("""
            CREATE TABLE medications (
                medication_id INT PRIMARY KEY,
                patient_id INT, encounter_id INT,
                name VARCHAR(50), dose VARCHAR(20), frequency VARCHAR(20),
                route VARCHAR(20), status VARCHAR(20), prescribed_at TIMESTAMP
            )"""))

    _bulk_upsert_pg(e, "patients",     "patient_id",     _patients())
    _bulk_upsert_pg(e, "encounters",   "encounter_id",   _encounters())
    _bulk_upsert_pg(e, "lab_results",  "lab_result_id",  _lab_results())
    _bulk_upsert_pg(e, "medications",  "medication_id",  _medications())
    e.dispose()


def _bulk_upsert_pg(engine, table, pk, rows):
    if not rows:
        return
    cols = list(rows[0])
    csv = ", ".join(cols)
    binds = ", ".join(f":{c}" for c in cols)
    upd = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c != pk)
    sql = (f"INSERT INTO {table} ({csv}) VALUES ({binds}) "
           f"ON CONFLICT ({pk}) DO UPDATE SET {upd}")
    with engine.begin() as c:
        for r in rows:
            c.execute(text(sql), r)
    log.info("  [pg] %s -> %d rows upserted", table, len(rows))


def _seed_mysql(cs: str) -> None:
    sa = "mysql+pymysql://" + cs[len("mysql://"):]
    log.info("[mysql] connecting %s", _redact(cs))
    e = create_engine(sa, pool_pre_ping=True)
    with e.begin() as c:
        # MySQL: disable FK checks during drop to side-step CDC trigger deps
        c.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in ("medications", "lab_results", "encounters", "patients"):
            c.execute(text(f"DROP TABLE IF EXISTS `{t}`"))
        c.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        c.execute(text("""
            CREATE TABLE patients (
                patient_id INT PRIMARY KEY,
                mrn VARCHAR(20) UNIQUE,
                first_name VARCHAR(50), last_name VARCHAR(50),
                date_of_birth DATE, gender CHAR(1)
            ) ENGINE=InnoDB"""))
        c.execute(text("""
            CREATE TABLE encounters (
                encounter_id INT PRIMARY KEY,
                patient_id INT,
                encounter_type VARCHAR(20), status VARCHAR(20),
                start_date DATE, end_date DATE
            ) ENGINE=InnoDB"""))
        c.execute(text("""
            CREATE TABLE lab_results (
                lab_result_id INT PRIMARY KEY,
                patient_id INT, encounter_id INT,
                test_name VARCHAR(50), test_value DECIMAL(10,3), test_unit VARCHAR(20),
                status VARCHAR(20), observed_at DATETIME
            ) ENGINE=InnoDB"""))
        c.execute(text("""
            CREATE TABLE medications (
                medication_id INT PRIMARY KEY,
                patient_id INT, encounter_id INT,
                name VARCHAR(50), dose VARCHAR(20), frequency VARCHAR(20),
                route VARCHAR(20), status VARCHAR(20), prescribed_at DATETIME
            ) ENGINE=InnoDB"""))

    for tbl, rows in [("patients", _patients()), ("encounters", _encounters()),
                      ("lab_results", _lab_results()), ("medications", _medications())]:
        _bulk_upsert_mysql(e, tbl, rows)
    e.dispose()


def _bulk_upsert_mysql(engine, table, rows):
    if not rows:
        return
    cols = list(rows[0])
    csv = ", ".join(f"`{c}`" for c in cols)
    binds = ", ".join(f":{c}" for c in cols)
    upd = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in cols)
    sql = f"INSERT INTO `{table}` ({csv}) VALUES ({binds}) ON DUPLICATE KEY UPDATE {upd}"
    with engine.begin() as c:
        for r in rows:
            c.execute(text(sql), r)
    log.info("  [mysql] %s -> %d rows upserted", table, len(rows))


def _seed_mongodb(cs: str) -> None:
    from pymongo import MongoClient, UpdateOne
    log.info("[mongo] connecting %s", _redact(cs))
    cli = MongoClient(cs, serverSelectionTimeoutMS=5000)
    db = cli["hospital_db_mongodb"]
    # Drop legacy collections so old indexes (e.g. unique medical_record_number)
    # don't conflict with the demo dataset.
    for coll in ("patients", "encounters", "lab_results", "medications"):
        db.drop_collection(coll)
    for coll, rows, pk in [
        ("patients",     _patients(),    "patient_id"),
        ("encounters",   _encounters(),  "encounter_id"),
        ("lab_results",  _lab_results(), "lab_result_id"),
        ("medications",  _medications(), "medication_id"),
    ]:
        ops = [UpdateOne({pk: r[pk]}, {"$set": _mongo_normalize(r)}, upsert=True)
               for r in rows]
        if ops:
            res = db[coll].bulk_write(ops, ordered=False)
            log.info("  [mongo] %s -> upserted=%d modified=%d",
                     coll, res.upserted_count, res.modified_count)
    cli.close()


def _mongo_normalize(r):
    out = {}
    for k, v in r.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _seed_oracle(cs: str) -> None:
    from cdc.adapter_factory import CDCAdapterFactory
    log.info("[oracle] connecting %s", _redact(cs))
    a = CDCAdapterFactory.create_adapter(cs)
    a.connect()
    e = a.engine

    with e.begin() as c:
        for ddl in [
            """BEGIN EXECUTE IMMEDIATE 'CREATE TABLE patients (
                patient_id NUMBER PRIMARY KEY,
                mrn VARCHAR2(20) UNIQUE,
                first_name VARCHAR2(50), last_name VARCHAR2(50),
                date_of_birth DATE, gender CHAR(1))';
              EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF; END;""",
            """BEGIN EXECUTE IMMEDIATE 'CREATE TABLE encounters (
                encounter_id NUMBER PRIMARY KEY,
                patient_id NUMBER,
                encounter_type VARCHAR2(20), status VARCHAR2(20),
                start_date DATE, end_date DATE)';
              EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF; END;""",
            """BEGIN EXECUTE IMMEDIATE 'CREATE TABLE lab_results (
                lab_result_id NUMBER PRIMARY KEY,
                patient_id NUMBER, encounter_id NUMBER,
                test_name VARCHAR2(50), test_value NUMBER(10,3),
                test_unit VARCHAR2(20), status VARCHAR2(20), observed_at TIMESTAMP)';
              EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF; END;""",
            """BEGIN EXECUTE IMMEDIATE 'CREATE TABLE medications (
                medication_id NUMBER PRIMARY KEY,
                patient_id NUMBER, encounter_id NUMBER,
                name VARCHAR2(50), dose VARCHAR2(20), frequency VARCHAR2(20),
                route VARCHAR2(20), status VARCHAR2(20), prescribed_at TIMESTAMP)';
              EXCEPTION WHEN OTHERS THEN IF SQLCODE != -955 THEN RAISE; END IF; END;""",
        ]:
            c.execute(text(ddl))

    for tbl, pk, rows in [
        ("patients",     "patient_id",     _patients()),
        ("encounters",   "encounter_id",   _encounters()),
        ("lab_results",  "lab_result_id",  _lab_results()),
        ("medications",  "medication_id",  _medications()),
    ]:
        a.load_data(tbl, rows, upsert_keys=[pk])
        log.info("  [oracle] %s -> %d rows upserted", tbl, len(rows))
    a.close()


def _seed_sqlserver(cs: str) -> None:
    from cdc.adapter_factory import CDCAdapterFactory
    log.info("[mssql] connecting %s", _redact(cs))
    a = CDCAdapterFactory.create_adapter(cs)
    a.connect()
    e = a.engine
    with e.begin() as c:
        # Drop existing CDC triggers + tables to avoid legacy-schema collisions
        for t in ("medications", "lab_results", "encounters", "patients"):
            c.execute(text(
                f"IF OBJECT_ID('trg_{t}_cdc','TR') IS NOT NULL "
                f"DROP TRIGGER trg_{t}_cdc"
            ))
            c.execute(text(
                f"IF OBJECT_ID('{t}','U') IS NOT NULL DROP TABLE {t}"
            ))
        c.execute(text("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='patients')
            CREATE TABLE patients (
                patient_id INT PRIMARY KEY,
                mrn NVARCHAR(20),
                first_name NVARCHAR(50), last_name NVARCHAR(50),
                date_of_birth DATE, gender CHAR(1))
        """))
        c.execute(text("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='encounters')
            CREATE TABLE encounters (
                encounter_id INT PRIMARY KEY,
                patient_id INT,
                encounter_type NVARCHAR(20), status NVARCHAR(20),
                start_date DATE, end_date DATE)
        """))
        c.execute(text("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='lab_results')
            CREATE TABLE lab_results (
                lab_result_id INT PRIMARY KEY,
                patient_id INT, encounter_id INT,
                test_name NVARCHAR(50), test_value DECIMAL(10,3),
                test_unit NVARCHAR(20), status NVARCHAR(20),
                observed_at DATETIME2)
        """))
        c.execute(text("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='medications')
            CREATE TABLE medications (
                medication_id INT PRIMARY KEY,
                patient_id INT, encounter_id INT,
                name NVARCHAR(50), dose NVARCHAR(20), frequency NVARCHAR(20),
                route NVARCHAR(20), status NVARCHAR(20),
                prescribed_at DATETIME2)
        """))

    for tbl, pk, rows in [
        ("patients",     "patient_id",     _patients()),
        ("encounters",   "encounter_id",   _encounters()),
        ("lab_results",  "lab_result_id",  _lab_results()),
        ("medications",  "medication_id",  _medications()),
    ]:
        a.load_data(tbl, rows, upsert_keys=[pk])
        log.info("  [mssql] %s -> %d rows upserted", tbl, len(rows))
    a.close()


def _redact(cs: str) -> str:
    if "://" not in cs: return cs
    s, rest = cs.split("://", 1)
    if "@" not in rest: return cs
    creds, host = rest.rsplit("@", 1)
    if ":" in creds:
        u, _ = creds.split(":", 1)
        return f"{s}://{u}:***@{host}"
    return cs


# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=None,
                        help="Comma list of: pg,mysql,mongo,oracle,mssql")
    args = parser.parse_args()

    DEFAULTS = {
        "pg":      "postgresql://hospital_user:hospital_pass@localhost:5435/hospital_db",
        "mysql":   "mysql://hospital_user:hospital_pass@localhost:3306/hospital_db_mysql",
        "mongo":   "mongodb://localhost:27017/hospital_db_mongodb",
        "oracle":  "oracle://hospital_user:hospital_pass@localhost:1521/XEPDB1",
        "mssql":   "sqlserver://sa:YourStrong@Passw0rd@localhost:1433/hospital_db_sqlserver",
    }

    seeders = {
        "pg":     _seed_postgres,
        "mysql":  _seed_mysql,
        "mongo":  _seed_mongodb,
        "oracle": _seed_oracle,
        "mssql":  _seed_sqlserver,
    }

    targets = (args.only.split(",") if args.only
               else list(seeders))
    failures = 0
    for t in targets:
        t = t.strip()
        if t not in seeders:
            log.warning("Unknown target %s — skipping", t)
            continue
        try:
            seeders[t](DEFAULTS[t])
            log.info("[%s] OK", t)
        except Exception as exc:
            failures += 1
            log.error("[%s] FAILED: %s", t, exc, exc_info=False)
    return failures


if __name__ == "__main__":
    sys.exit(main())
