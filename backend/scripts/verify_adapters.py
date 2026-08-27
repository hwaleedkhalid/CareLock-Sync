#!/usr/bin/env python3
"""
verify_adapters.py — multi-database adapter verification harness.

Runs the same five-step smoke test against every database declared in
``config/sync_config.json``:

  1. Factory resolves connection-string scheme → adapter class
  2. ``adapter.connect()`` succeeds
  3. ``adapter.validate_connection()`` returns True
  4. ``adapter.fetch_schema()`` returns ≥0 tables
  5. ``adapter.extract_data(<first table>, limit=3)`` returns rows

For each step the harness prints either ``[OK]`` or a one-line error.
Exit-code is the count of databases that failed any step (0 = green).

Usage:
    cd backend
    python scripts/verify_adapters.py                      # all sources
    python scripts/verify_adapters.py --only postgres,mysql
    python scripts/verify_adapters.py --skip-extract
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List

_THIS = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_THIS)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from cdc.adapter_factory import CDCAdapterFactory  # noqa: E402

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


# ── helpers ─────────────────────────────────────────────────────────────────
def _line(char: str = "-", n: int = 70) -> str:
    return char * n


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _err(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _info(msg: str) -> None:
    print(f"  [..]   {msg}")


def _redact(cs: str) -> str:
    """Redact the password portion of a URL for safe printing."""
    if "://" not in cs:
        return cs
    scheme, rest = cs.split("://", 1)
    if "@" not in rest:
        return cs
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        creds = f"{user}:***"
    return f"{scheme}://{creds}@{host}"


# ── per-source check ────────────────────────────────────────────────────────
def verify_source(source: Dict[str, Any], skip_extract: bool = False) -> bool:
    cs   = source["connection_string"]
    sid  = source.get("id", "<unnamed>")
    tabs = source.get("tables") or source.get("collections") or []

    print(_line("─"))
    print(f"  Source : {sid}")
    print(f"  URL    : {_redact(cs)}")

    failed = False

    # 1. Factory
    t0 = time.time()
    try:
        adapter = CDCAdapterFactory.create_adapter(cs)
        _ok(f"factory → {adapter.__class__.__name__}  "
            f"(detected: {CDCAdapterFactory.detect_database_type(cs)})  "
            f"[{(time.time()-t0)*1000:.0f}ms]")
    except Exception as exc:
        _err(f"factory failed: {exc}")
        return True  # this counts as a failure

    # 2. Connect
    t0 = time.time()
    try:
        adapter.connect()
        _ok(f"connect()  [{(time.time()-t0)*1000:.0f}ms]")
    except Exception as exc:
        _err(f"connect() failed: {exc}")
        adapter.close() if hasattr(adapter, "close") else None
        return True

    # 3. Validate
    t0 = time.time()
    if adapter.validate_connection():
        _ok(f"validate_connection()  [{(time.time()-t0)*1000:.0f}ms]")
    else:
        _err("validate_connection() returned False")
        failed = True

    # 4. Schema
    t0 = time.time()
    try:
        schema = adapter.fetch_schema()
        nt = schema.get("total_tables", 0)
        _ok(f"fetch_schema() → {nt} tables  [{(time.time()-t0)*1000:.0f}ms]")
        if nt:
            sample = list(schema["tables"].keys())[:5]
            _info(f"      e.g. {sample}")
    except Exception as exc:
        _err(f"fetch_schema() failed: {exc}")
        failed = True
        schema = None

    # 5. Extract
    if skip_extract:
        _info("skipping extract (--skip-extract)")
    else:
        # Pick a table: prefer the first declared in config, else any from schema
        target = tabs[0] if tabs else (
            next(iter(schema["tables"])) if schema and schema["tables"] else None
        )
        if not target:
            _info("no tables to extract from")
        else:
            t0 = time.time()
            try:
                rows = adapter.extract_data(target, limit=3)
                _ok(f"extract_data({target!r}, limit=3) → {len(rows)} rows  "
                    f"[{(time.time()-t0)*1000:.0f}ms]")
                if rows:
                    cols = list(rows[0].keys())[:6]
                    _info(f"      cols sample: {cols}")
            except Exception as exc:
                _err(f"extract_data({target!r}) failed: {exc}")
                failed = True

    # cleanup
    try:
        adapter.close()
    except Exception:
        pass

    return failed


# ── main ────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--config", default=None,
                        help="Path to sync_config.json (default: config/sync_config.json)")
    parser.add_argument("--only", default=None,
                        help="Comma-separated source IDs to test")
    parser.add_argument("--skip-extract", action="store_true",
                        help="Skip data-extraction step")
    args = parser.parse_args()

    cfg_path = args.config or os.path.join(
        _BACKEND, "..", "config", "sync_config.json"
    )
    cfg_path = os.path.abspath(cfg_path)
    if not os.path.exists(cfg_path):
        print(f"[FATAL] config file not found: {cfg_path}")
        return 99

    # config files written on Windows often carry a UTF-8 BOM
    with open(cfg_path, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)

    sources: List[Dict[str, Any]] = cfg.get("sources", [])
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        sources = [s for s in sources if s.get("id") in wanted]

    print(_line("=", 70))
    print(" CareLock-Sync Multi-DB Adapter Verification")
    print(f" Config: {cfg_path}")
    print(f" Sources to test: {len(sources)} "
          f"({', '.join(s.get('id', '?') for s in sources)})")
    print(_line("=", 70))

    failures = 0
    summary: List[str] = []
    for src in sources:
        failed = verify_source(src, skip_extract=args.skip_extract)
        if failed:
            failures += 1
            summary.append(f"  [FAIL]  {src.get('id')}")
        else:
            summary.append(f"  [OK  ]  {src.get('id')}")

    print(_line("=", 70))
    print(" SUMMARY")
    print(_line("-", 70))
    for line in summary:
        print(line)
    print(_line("-", 70))
    print(f"  {len(sources) - failures}/{len(sources)} sources passed all checks")
    coverage = CDCAdapterFactory.get_coverage_percentage(
        list({CDCAdapterFactory.detect_database_type(s["connection_string"])
              for s in sources if s.get("id") not in
              {sources[i].get("id") for i in range(len(sources))
               if i < failures}})
    )
    print(f"  Real-world hospital coverage of GREEN sources: ~{coverage}%")
    print(_line("═"))

    return failures


if __name__ == "__main__":
    sys.exit(main())
