"""
HMAC-SHA256 signing for CDC Worker → Ingestion HTTP push.

Wire format:
  Body  : raw JSON bytes (deterministic, no whitespace).
  Header: X-CDC-Source: <source_id>
  Header: X-CDC-Timestamp: <unix_seconds>
  Header: X-CDC-Signature: hex(hmac_sha256(key, f"{source_id}.{timestamp}.{body}"))
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Tuple


_MAX_SKEW_SECONDS = 300   # ±5 minutes


def sign(source_id: str, body: bytes, key: str, *, ts: int | None = None) -> Tuple[int, str]:
    """Produce (timestamp, hex_signature) for a body."""
    timestamp = int(ts if ts is not None else time.time())
    msg = f"{source_id}.{timestamp}.".encode("utf-8") + body
    sig = hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return timestamp, sig


def verify(
    source_id: str,
    body: bytes,
    key: str,
    timestamp: int,
    signature: str,
    *,
    now: int | None = None,
) -> bool:
    """
    Constant-time verify. Returns True iff signature matches AND timestamp
    is within +/- _MAX_SKEW_SECONDS of `now` (defaults to system time).
    """
    current = int(now if now is not None else time.time())
    if abs(current - int(timestamp)) > _MAX_SKEW_SECONDS:
        return False
    msg = f"{source_id}.{int(timestamp)}.".encode("utf-8") + body
    expected = hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
