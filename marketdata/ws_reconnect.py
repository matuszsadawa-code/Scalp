from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    initial_delay_s: float
    max_delay_s: float
    backoff_multiplier: float
    jitter_max_ms: int


class ReconnectBackoff:
    def __init__(self, policy: ReconnectPolicy, *, seed: int = 7) -> None:
        self._policy = policy
        self._attempt = 0
        self._random = random.Random(seed)

    def reset(self) -> None:
        self._attempt = 0

    def next_delay_s(self) -> float:
        base = self._policy.initial_delay_s * (self._policy.backoff_multiplier ** self._attempt)
        self._attempt += 1
        capped = min(base, self._policy.max_delay_s)
        jitter = self._random.uniform(0.0, float(self._policy.jitter_max_ms) / 1000.0)
        return capped + jitter
