"""
CareLock Sync — CDC Client Agent
=================================
Runs on the HOSPITAL's local machine.
Polls the local hospital database for changes and pushes them to the
CareLock central server via HTTP.

Design:
  - Zero dependencies beyond requests + sqlalchemy (already in requirements.txt)
  - Watermark persistence in a local JSON file
  - Configurable via cdc_agent_config.json OR command-line args
  - Graceful error recovery with exponential back-off
  - Secure: API key auth, all traffic over HTTPS in production

Usage:
  python cdc_agent.py                          # use cdc_agent_config.json
  python cdc_agent.py --interval 3             # poll every 3 seconds
  python cdc_agent.py --reset                  # reset watermark, full re-sync
  python cdc_agent.py --test                   # test connectivity and exit

Configuration file (cdc_agent_config.json):
{
    "central_api_url":  "http://localhost:8000",
    "api_key":          "clk-cgh001-hospital-key",
    "tenant_id":        1,
    "poll_interval":    5,
    "hospital_db_url":  "postgresql://hospital_user:hospital_pass@localhost:5432/hospital_db",
    "tables_to_monitor": ["patients", "encounters", "lab_results", "medications"],
    "watermark_file":   "cdc_agent_watermark.json",
    "log_level":        "INFO"
}
"""
import os
import sys
import json
import time
import logging
import argparse
import threading
import signal
from datetime import datetime
from typing import Optional, Dict, List, Any

# Add backend to path so we can reuse existing CDC adapters
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

try:
    import requests
except ImportError:
    print("[ERROR] requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    from sqlalchemy import create_engine, text
    _sqlalchemy_available = True
except ImportError:
    _sqlalchemy_available = False
    print("[WARN] SQLAlchemy not available — DB polling disabled")

# ── Default config ─────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "central_api_url":   "http://localhost:8000",
    "api_key":           "clk-cgh001-hospital-key",
    "tenant_id":         1,
    "poll_interval":     5,
    "hospital_db_url":   "postgresql://hospital_user:hospital_pass@localhost:5432/hospital_db",
    "tables_to_monitor": ["patients", "encounters", "lab_results", "medications"],
    "watermark_file":    "cdc_agent_watermark.json",
    "log_level":         "INFO",
    "batch_size":        100,
    "max_retries":       3,
    "retry_backoff":     2.0,
}

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "cdc_agent_config.json")
WATERMARK_FILE = "cdc_agent_watermark.json"


def load_config() -> Dict:
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                file_cfg = json.load(f)
            config.update(file_cfg)
            print(f"[CONFIG] Loaded from {CONFIG_FILE}")
        except Exception as e:
            print(f"[WARN] Could not load {CONFIG_FILE}: {e} — using defaults")
    return config


def save_default_config():
    """Write a default config file if one doesn't exist."""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"[CONFIG] Created default config at {CONFIG_FILE}")
        print("         Edit it with your hospital DB credentials and API key before running.")


class WatermarkStore:
    """Persist per-table watermarks to a local JSON file."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._data: Dict[str, int] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        try:
            with open(self.filepath, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logging.warning(f"Could not save watermark: {e}")

    def get(self, table: str) -> int:
        return self._data.get(table, 0)

    def set(self, table: str, change_id: int):
        self._data[table] = change_id
        self._save()

    def reset(self):
        self._data = {}
        self._save()
        logging.info("Watermarks reset to 0")


class CDCAgent:
    """
    Client-side CDC agent.
    Reads from local hospital DB, pushes changes to central CareLock API.
    """

    def __init__(self, config: Dict):
        self.cfg = config
        self.api_url = config["central_api_url"].rstrip("/")
        self.api_key = config["api_key"]
        self.tenant_id = config["tenant_id"]
        self.poll_interval = config["poll_interval"]
        self.tables = config["tables_to_monitor"]
        self.batch_size = config.get("batch_size", 100)
        self.watermark = WatermarkStore(config.get("watermark_file", WATERMARK_FILE))
        self._running = False
        self._session = requests.Session()
        self._session.headers.update({
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "X-CDC-Agent": "carelock-cdc-agent/1.0",
            "X-Tenant-Id": str(self.tenant_id),
        })

        # Stats
        self.stats = {
            "started_at": None,
            "cycles": 0,
            "changes_sent": 0,
            "errors": 0,
            "last_push_at": None,
        }

        # DB engine (lazy init)
        self._engine = None

    # ── DB connection ──────────────────────────────────────────────────────
    def _get_engine(self):
        if self._engine is None and _sqlalchemy_available:
            db_url = self.cfg.get("hospital_db_url")
            if db_url:
                self._engine = create_engine(db_url, pool_pre_ping=True, pool_size=2)
        return self._engine

    def _check_cdc_table(self) -> bool:
        """Verify data_change_log table exists in the hospital DB."""
        engine = self._get_engine()
        if not engine:
            return False
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM data_change_log LIMIT 1"))
            return True
        except Exception:
            return False

    def _fetch_changes(self, table: str, since_id: int) -> List[Dict]:
        """Pull rows from data_change_log for a specific table since last watermark."""
        engine = self._get_engine()
        if not engine:
            return []
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT change_id, table_name, operation,
                           record_id, old_data, new_data, changed_at
                    FROM data_change_log
                    WHERE table_name = :tbl
                      AND change_id  > :since
                    ORDER BY change_id
                    LIMIT :lim
                """), {"tbl": table, "since": since_id, "lim": self.batch_size})
                return [
                    {
                        "change_id": r[0],
                        "table_name": r[1],
                        "operation": r[2],
                        "record_id": r[3],
                        "old_data": r[4] if r[4] else {},
                        "new_data": r[5] if r[5] else {},
                        "changed_at": r[6].isoformat() if r[6] else datetime.utcnow().isoformat(),
                        "tenant_id": self.tenant_id,
                    }
                    for r in rows
                ]
        except Exception as e:
            logging.error(f"DB fetch error for {table}: {e}")
            return []

    # ── API push ───────────────────────────────────────────────────────────
    def _push_changes(self, changes: List[Dict]) -> bool:
        """POST a batch of change events to the central API."""
        if not changes:
            return True
        try:
            resp = self._session.post(
                f"{self.api_url}/api/v1/cdc/ingest",
                json={"tenant_id": self.tenant_id, "changes": changes},
                timeout=10,
            )
            if resp.status_code == 200:
                self.stats["changes_sent"] += len(changes)
                self.stats["last_push_at"] = datetime.utcnow().isoformat()
                return True
            elif resp.status_code == 404:
                # /api/v1/cdc/ingest not yet implemented — fall back to incremental sync trigger
                return self._trigger_incremental_sync()
            else:
                logging.warning(f"API push returned {resp.status_code}: {resp.text[:200]}")
                return False
        except requests.exceptions.ConnectionError:
            logging.warning(f"Cannot reach central API at {self.api_url} — will retry")
            return False
        except Exception as e:
            logging.error(f"Push error: {e}")
            return False

    def _trigger_incremental_sync(self) -> bool:
        """
        Fallback: tell the server to pull via its own incremental sync endpoint.
        Works even before /cdc/ingest is implemented.
        """
        try:
            resp = self._session.post(
                f"{self.api_url}/api/v1/sync/incremental",
                json={"tenant_id": self.tenant_id},
                timeout=15,
            )
            return resp.status_code == 200
        except Exception as e:
            logging.debug(f"Incremental sync trigger: {e}")
            return False

    # ── Connectivity test ──────────────────────────────────────────────────
    def test_connectivity(self) -> bool:
        print("\n" + "=" * 60)
        print("  CDC Agent — Connectivity Test")
        print("=" * 60)

        # 1. Central API health
        print(f"\n[1] Central API:  {self.api_url}")
        try:
            r = self._session.get(f"{self.api_url}/health", timeout=5)
            if r.status_code == 200:
                print(f"    Status: OK ({r.json().get('status', 'healthy')})")
            else:
                print(f"    Status: HTTP {r.status_code}")
        except Exception as e:
            print(f"    Status: FAILED — {e}")

        # 2. API key auth
        print(f"\n[2] API Key auth: {self.api_key[:12]}...")
        try:
            r = self._session.get(f"{self.api_url}/api/v1/sync/status", timeout=5)
            if r.status_code == 200:
                print("    Status: OK — key accepted")
            elif r.status_code == 401:
                print("    Status: FAILED — invalid API key")
            else:
                print(f"    Status: HTTP {r.status_code}")
        except Exception as e:
            print(f"    Status: ERROR — {e}")

        # 3. Local hospital DB
        print(f"\n[3] Hospital DB:  {self.cfg.get('hospital_db_url', 'not configured')[:40]}...")
        if self._get_engine():
            try:
                engine = self._get_engine()
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                print("    Status: OK — connected")
                if self._check_cdc_table():
                    print("    CDC log table: FOUND (data_change_log)")
                else:
                    print("    CDC log table: NOT FOUND — run hospital DB setup SQL first")
            except Exception as e:
                print(f"    Status: FAILED — {e}")
        else:
            print("    Status: SQLAlchemy not available")

        print("\n" + "=" * 60)
        return True

    # ── Main loop ──────────────────────────────────────────────────────────
    def _poll_once(self):
        """One full poll cycle across all monitored tables."""
        any_changes = False
        for table in self.tables:
            since = self.watermark.get(table)
            changes = self._fetch_changes(table, since)
            if not changes:
                continue
            max_id = max(c["change_id"] for c in changes)
            if self._push_changes(changes):
                self.watermark.set(table, max_id)
                logging.info(
                    f"[{table}] Pushed {len(changes)} changes "
                    f"(watermark {since} → {max_id})"
                )
                any_changes = True
            else:
                # Don't advance watermark if push failed
                self.stats["errors"] += 1
        if any_changes:
            self.stats["cycles"] += 1

    def start(self):
        self._running = True
        self.stats["started_at"] = datetime.utcnow().isoformat()

        print("=" * 70)
        print("  CareLock Sync — CDC Client Agent  v1.0")
        print("=" * 70)
        print(f"  Central API  : {self.api_url}")
        print(f"  Tenant ID    : {self.tenant_id}")
        print(f"  Poll interval: {self.poll_interval}s")
        print(f"  Tables       : {', '.join(self.tables)}")
        print(f"  Watermark    : {self.watermark.filepath}")
        print("=" * 70)
        print("  Running — press Ctrl+C to stop")
        print()

        # Stats reporter thread
        def _report():
            while self._running:
                time.sleep(60)
                uptime = int((datetime.utcnow() - datetime.fromisoformat(
                    self.stats["started_at"])).total_seconds())
                print(
                    f"[STATS] uptime={uptime}s  cycles={self.stats['cycles']}  "
                    f"changes_sent={self.stats['changes_sent']}  "
                    f"errors={self.stats['errors']}"
                )

        threading.Thread(target=_report, daemon=True).start()

        back_off = self.poll_interval
        while self._running:
            try:
                self._poll_once()
                back_off = self.poll_interval  # reset back-off on success
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.stats["errors"] += 1
                logging.error(f"Poll error: {e}")
                back_off = min(back_off * 2, 60)
            time.sleep(back_off)

    def stop(self):
        self._running = False
        print("\n[CDC Agent] Stopped.")
        print(f"  Changes sent : {self.stats['changes_sent']}")
        print(f"  Errors       : {self.stats['errors']}")
        print(f"  Cycles       : {self.stats['cycles']}")


# ── Entry point ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="CareLock CDC Client Agent")
    parser.add_argument("--interval",   type=int,   help="Poll interval in seconds (default: 5)")
    parser.add_argument("--api-url",    type=str,   help="Central API URL")
    parser.add_argument("--api-key",    type=str,   help="API key (X-API-Key)")
    parser.add_argument("--tenant-id",  type=int,   help="Tenant ID")
    parser.add_argument("--db-url",     type=str,   help="Hospital DB URL")
    parser.add_argument("--reset",      action="store_true", help="Reset watermarks to 0")
    parser.add_argument("--test",       action="store_true", help="Test connectivity and exit")
    parser.add_argument("--init-config",action="store_true", help="Create default config file and exit")
    args = parser.parse_args()

    if args.init_config:
        save_default_config()
        return

    config = load_config()

    # CLI overrides
    if args.interval:   config["poll_interval"]  = args.interval
    if args.api_url:    config["central_api_url"] = args.api_url
    if args.api_key:    config["api_key"]          = args.api_key
    if args.tenant_id:  config["tenant_id"]        = args.tenant_id
    if args.db_url:     config["hospital_db_url"]  = args.db_url

    logging.basicConfig(
        level=getattr(logging, config.get("log_level", "INFO")),
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    agent = CDCAgent(config)

    if args.reset:
        agent.watermark.reset()
        print("[OK] Watermarks reset.")
        return

    if args.test:
        agent.test_connectivity()
        return

    # Graceful shutdown on SIGINT / SIGTERM
    def _signal_handler(sig, frame):
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    agent.start()


if __name__ == "__main__":
    main()
