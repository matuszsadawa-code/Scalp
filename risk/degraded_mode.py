from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VenueHealth:
    bybit_public_ok: bool
    bybit_private_ok: bool
    binance_ok: bool
    metadata_fresh: bool
    book_valid: bool


@dataclass(frozen=True, slots=True)
class DegradedDecision:
    allow_new_entries: bool
    force_reduced_risk: bool
    reason: str


def evaluate_degraded_mode(health: VenueHealth) -> DegradedDecision:
    if not health.metadata_fresh:
        return DegradedDecision(False, True, "metadata_stale")
    if not health.book_valid:
        return DegradedDecision(False, True, "book_invalid")
    if not health.bybit_private_ok:
        return DegradedDecision(False, True, "private_ws_degraded")
    if not health.bybit_public_ok:
        return DegradedDecision(False, True, "bybit_public_degraded")
    if not health.binance_ok:
        return DegradedDecision(True, True, "binance_degraded")
    return DegradedDecision(True, False, "fully_operational")
