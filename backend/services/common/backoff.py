"""Backoff helpers shared by CDC Worker and ETL Worker."""
from __future__ import annotations

import random


def exp_backoff_ms(
    attempt: int,
    *,
    initial_ms: int,
    max_ms: int,
    jitter_pct: int = 20,
) -> int:
    """
    Compute milliseconds to wait before retry attempt N (1-indexed).
    1 → initial_ms, 2 → 2*initial_ms, ..., capped at max_ms.
    Jitter: ±jitter_pct%.
    """
    if attempt < 1:
        attempt = 1
    base = min(initial_ms * (2 ** (attempt - 1)), max_ms)
    if jitter_pct <= 0:
        return base
    spread = base * jitter_pct / 100.0
    delta = random.uniform(-spread, spread)
    return max(1, int(base + delta))
