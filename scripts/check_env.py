import sys, os
sys.path.insert(0, r"C:\Projects\CareLock-Sync\backend")
checks = {}
def chk(label, fn):
    try:
        r = fn(); checks[label] = "OK  " + str(r or "")
    except Exception as e:
        checks[label] = "FAIL: " + str(e)

chk("python_version",  lambda: sys.version.split()[0])
chk("cryptography",    lambda: __import__("cryptography").__version__)
chk("psycopg2",        lambda: __import__("psycopg2").__version__)
chk("sqlalchemy",      lambda: __import__("sqlalchemy").__version__)
chk("fastapi",         lambda: __import__("fastapi").__version__)
chk("pydantic",        lambda: __import__("pydantic").__version__)
chk("faker",           lambda: __import__("faker").__version__)
chk("pytest",          lambda: __import__("pytest").__version__)
chk("config",          lambda: __import__("common.config", fromlist=["settings"]).settings.APP_NAME)
chk("cdc_monitor_import", lambda: str(__import__("connector.cdc_monitor", fromlist=["CDCMonitor"]).CDCMonitor))

from common.config import settings
from sqlalchemy import create_engine, text
for label, url in [("hospital_db", settings.hospital_db_url), ("shared_db", settings.shared_db_url)]:
    try:
        eng = create_engine(url, connect_args={"connect_timeout": 3})
        with eng.connect() as c:
            v = c.execute(text("SELECT version()")).scalar()
        checks[label] = "OK  " + v[:60]
    except Exception as e:
        checks[label] = "FAIL: " + str(e)[:80]

print("="*60)
print("ENVIRONMENT CHECK")
print("="*60)
for k,v in checks.items():
    print(f"  {'OK' if v.startswith('OK') else 'XX'} {k:30s} {v}")
fails = [k for k,v in checks.items() if not v.startswith("OK")]
print(f"\nResult: {'ALL PASSED' if not fails else 'FAILURES: ' + str(fails)}")