"""
CDC Worker — one process per source DB.

Run:
    python -m services.cdc_worker --source hospital_a
    python -m services.cdc_worker --source hospital_a --setup

Reuses connector.cdc_monitor.CDCMonitor for all CDC SQL — never duplicates
trigger or query logic. The watermark used here is the per-(source,table)
watermark stored in the SHARED DB (different table from the legacy hospital
cdc_watermarks keyed by tenant_id).

Exit codes:
   0 — graceful shutdown
   2 — cannot connect to source DB
   3 — CDC objects missing and --setup not requested
   4 — ingestion endpoint unreachable
   5 — auth (HMAC) misconfigured
   6 — table registry missing for configured tables
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from typing import Optional

# path bootstrap
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _BACKEND)

from services.common import config as cfg                     # noqa: E402
from services.common.schema import apply_schema                # noqa: E402
from services.cdc_worker.worker import CDCWorker               # noqa: E402
from services.cdc_worker.admin import start_admin_server       # noqa: E402

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","service":"cdc_worker","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger("cdc.worker")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CareLock CDC Worker")
    p.add_argument("--source", required=True, help="source id from cdc_sources.yaml")
    p.add_argument("--setup", action="store_true",
                   help="install missing CDC objects (triggers, log table) before run")
    p.add_argument("--once", action="store_true",
                   help="run a single polling cycle and exit (testing)")
    return p.parse_args()


def _install_signal_handlers(worker: CDCWorker) -> None:
    def _stop(signum, frame):
        logger.info("shutdown signal=%s", signum)
        worker.request_stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _stop)
        except (ValueError, OSError):
            # not in main thread on Windows — ignore
            pass


def main() -> int:
    args = _parse_args()
    try:
        source = cfg.load_source(args.source)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        logger.error("config error: %s", exc)
        return 1

    # Apply shared-DB schema (new watermark + inbox tables) — idempotent.
    try:
        apply_schema(cfg.shared_db_url())
    except Exception as exc:
        logger.error("shared schema apply failed: %s", exc)
        return 4

    try:
        hmac_key = source.resolved_auth_key()
    except ValueError as exc:
        logger.error("hmac config error: %s", exc)
        return 5

    worker = CDCWorker(source=source, hmac_key=hmac_key,
                       auto_setup=args.setup or source.auto_setup)

    rc = worker.preflight()
    if rc != 0:
        return rc

    _install_signal_handlers(worker)
    admin_thread = threading.Thread(
        target=start_admin_server,
        kwargs={"port": source.admin_port, "worker": worker},
        daemon=True,
        name="cdc-admin",
    )
    admin_thread.start()

    if args.once:
        worker.run_once()
        return 0
    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
