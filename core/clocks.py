from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalBucket:
    bucket_ms: int
    opened_at_ms: int


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def canonical_bucket(ts_ms: int, bucket_ms: int) -> CanonicalBucket:
    opened = (ts_ms // bucket_ms) * bucket_ms
    return CanonicalBucket(bucket_ms=bucket_ms, opened_at_ms=opened)
