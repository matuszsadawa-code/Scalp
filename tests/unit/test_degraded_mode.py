from __future__ import annotations

from risk.degraded_mode import VenueHealth, evaluate_degraded_mode


def test_binance_degraded_forces_reduced_without_full_stop() -> None:
    decision = evaluate_degraded_mode(
        VenueHealth(
            bybit_public_ok=True,
            bybit_private_ok=True,
            binance_ok=False,
            metadata_fresh=True,
            book_valid=True,
        )
    )
    assert decision.allow_new_entries
    assert decision.force_reduced_risk
    assert decision.reason == "binance_degraded"


def test_private_ws_degraded_stops_entries() -> None:
    decision = evaluate_degraded_mode(
        VenueHealth(
            bybit_public_ok=True,
            bybit_private_ok=False,
            binance_ok=True,
            metadata_fresh=True,
            book_valid=True,
        )
    )
    assert not decision.allow_new_entries
    assert decision.reason == "private_ws_degraded"
