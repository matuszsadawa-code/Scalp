from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegimeSnapshot:
    name: str
    confidence: float


def regime_allows_mean_reversion(snapshot: RegimeSnapshot) -> bool:
    if snapshot.confidence < 0.65:
        return False
    return snapshot.name in {"balanced", "rotational", "local_stretch"}
