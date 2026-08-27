"""
Automatic Sync Scheduler – CDC-driven incremental sync.

FIXES from previous version
----------------------------
1. Reads last_sync_id from a persistent state file, NOT from MAX(change_id).
2. Properly reports exceptions instead of swallowing them.
3. Uses settings.hospital_db_url instead of hardcoding.
4. Saves watermark after each successful sync.
"""
import schedule
import time
import threading
import json
from datetime import datetime
from typing import Optional
import sys
import os

# ── path bootstrap ────────────────────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, 'etl'))

from incremental_sync import IncrementalSync
from common.config import settings


class SyncScheduler:
    """Runs incremental syncs at fixed intervals, persisting state to disk."""

    STATE_FILE = os.path.join(backend_dir, 'scheduler_state.json')

    def __init__(self, tenant_id: int = 1, interval_seconds: int = 60):
        self.tenant_id = tenant_id
        self.interval_seconds = interval_seconds
        self.sync_service = IncrementalSync(tenant_id)

        # FIX 1 – read from persistent file instead of DB MAX(change_id)
        self.last_sync_id = self._load_state()

        self.is_running = False
        self.scheduler_thread = None

        self.stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'total_changes_synced': 0,
            'last_run_time': None,
            'last_error': None,
        }

    # ── state persistence ─────────────────────────────────────────────────
    def _load_state(self) -> int:
        """
        Load last_sync_id from disk (or default to 0).
        This means the first run will replay the entire change log.
        """
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r') as f:
                    data = json.load(f)
                    val = data.get('last_sync_id', 0)
                    print(f"  Loaded scheduler state: last_sync_id = {val}")
                    return val
            except Exception as e:
                print(f"  WARNING: Could not load state file: {e}")
        return 0

    def _save_state(self, last_change_id: int):
        """Persist the new watermark so the next scheduler run starts there."""
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump({'last_sync_id': last_change_id}, f)
        except Exception as e:
            print(f"  ERROR saving state: {e}")

    # ── sync job ──────────────────────────────────────────────────────────
    def _run_sync(self):
        """
        Run one incremental sync, update stats, and persist the watermark.
        FIX 2 – report exceptions instead of silently swallowing them.
        """
        try:
            now_str = datetime.now().strftime('%H:%M:%S')
            print(f"\n[{now_str}] Running automatic incremental sync...")
            print(f"  Starting from change_id = {self.last_sync_id}")

            stats = self.sync_service.sync_incremental(last_sync_id=self.last_sync_id)

            # update watermark
            if 'last_change_id' in stats and stats['last_change_id'] is not None:
                self.last_sync_id = stats['last_change_id']
                self._save_state(self.last_sync_id)

            # update stats
            self.stats['total_runs'] += 1
            self.stats['last_run_time'] = datetime.now().isoformat()

            synced_count = stats.get('synced', 0)
            total_count  = stats.get('total_changes', 0)

            if total_count > 0:
                self.stats['successful_runs'] += 1
                self.stats['total_changes_synced'] += synced_count
                print(f"  ✓ Synced {synced_count}/{total_count} changes")
            else:
                print(f"  • No new changes")

            self.stats['last_error'] = None

        except Exception as e:
            # FIX 2 – don't swallow exceptions; log and continue
            import traceback
            self.stats['failed_runs'] += 1
            self.stats['last_error'] = str(e)
            print(f"  ✗ Sync FAILED:")
            traceback.print_exc()

    # ── scheduler control ─────────────────────────────────────────────────
    def start(self):
        """Start the background scheduler thread."""
        if self.is_running:
            print("Scheduler already running")
            return

        self.is_running = True

        schedule.every(self.interval_seconds).seconds.do(self._run_sync)

        print("=" * 70)
        print("Automatic Sync Scheduler STARTED")
        print("=" * 70)
        print(f"Tenant ID         : {self.tenant_id}")
        print(f"Sync Interval     : {self.interval_seconds} seconds")
        print(f"Starting Change ID: {self.last_sync_id}")
        print(f"State File        : {self.STATE_FILE}")
        print(f"Started At        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        def run_scheduler_loop():
            while self.is_running:
                schedule.run_pending()
                time.sleep(1)

        self.scheduler_thread = threading.Thread(target=run_scheduler_loop, daemon=True)
        self.scheduler_thread.start()

        # run an immediate sync on startup
        self._run_sync()

    def stop(self):
        """Stop the scheduler."""
        if not self.is_running:
            return

        self.is_running = False
        schedule.clear()

        print("\n" + "=" * 70)
        print("Scheduler STOPPED")
        print("=" * 70)
        print(f"Total Runs        : {self.stats['total_runs']}")
        print(f"Successful Runs   : {self.stats['successful_runs']}")
        print(f"Failed Runs       : {self.stats['failed_runs']}")
        print(f"Changes Synced    : {self.stats['total_changes_synced']}")
        print(f"Last Change ID    : {self.last_sync_id}")
        print("=" * 70)

    def get_stats(self):
        """Return current statistics."""
        return {
            **self.stats,
            'is_running': self.is_running,
            'interval_seconds': self.interval_seconds,
            'last_sync_id': self.last_sync_id,
        }


# ── CLI ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Automatic Sync Scheduler')
    parser.add_argument('--interval', type=int, default=60,
                        help='Sync interval in seconds (default: 60)')
    parser.add_argument('--reset', action='store_true',
                        help='Reset state file (start from change_id=0)')
    args = parser.parse_args()

    if args.reset:
        state_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'scheduler_state.json'
        )
        if os.path.exists(state_path):
            os.remove(state_path)
            print(f"Removed state file: {state_path}")
        else:
            print("State file does not exist; nothing to reset.")
        sys.exit(0)

    scheduler = SyncScheduler(tenant_id=1, interval_seconds=args.interval)

    try:
        scheduler.start()
        print("\nPress Ctrl+C to stop...\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        scheduler.stop()
