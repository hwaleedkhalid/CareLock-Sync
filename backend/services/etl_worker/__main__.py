"""
ETL Worker — drains cdc_inbox into FHIR shared tables.

Run:
    python -m services.etl_worker
    python -m services.etl_worker --once

Ordering: claims one (source_id, table_name) partition at a time via
FOR UPDATE SKIP LOCKED, then iterates rows in source_seq order. Reuses
backend.etl.incremental_sync.IncrementalSync handlers for the actual
write path so ETL logic is not duplicated.
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _BACKEND)

from services.common.schema import apply_schema           # noqa: E402
from services.common.config import shared_db_url          # noqa: E402
from services.etl_worker.worker import ETLWorker          # noqa: E402
from services.etl_worker.admin import start_admin_server  # noqa: E402

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","service":"etl_worker","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger("cdc.etl")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CareLock ETL Worker")
    p.add_argument("--once", action="store_true",
                   help="claim one batch and exit (testing)")
    p.add_argument("--admin-port", type=int,
                   default=int(os.environ.get("ETL_ADMIN_PORT", "9201")))
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    try:
        apply_schema(shared_db_url())
    except Exception as exc:
        logger.error("schema apply failed: %s", exc)
        return 4

    worker = ETLWorker()

    def _stop(signum, frame):
        logger.info("shutdown signal=%s", signum)
        worker.request_stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _stop)
        except (ValueError, OSError):
            pass

    admin = threading.Thread(
        target=start_admin_server,
        kwargs={"port": args.admin_port, "worker": worker},
        daemon=True,
        name="etl-admin",
    )
    admin.start()

    if args.once:
        worker.process_one_partition()
        return 0
    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
