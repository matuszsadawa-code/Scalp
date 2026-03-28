from __future__ import annotations

from decimal import Decimal

from core.types import InstrumentConstraints
from risk.position_sizer import compute_position_size


CONSTRAINTS = InstrumentConstraints(
    symbol="BTCUSDT",
    tick_size=Decimal("0.10"),
    qty_step=Decimal("0.001"),
    min_qty=Decimal("0.001"),
    max_qty=Decimal("100"),
    min_price=Decimal("1000"),
    max_price=Decimal("1000000"),
)


def test_position_size_respects_leverage_cap_by_reducing_qty() -> None:
    result = compute_position_size(
        equity_usd=Decimal("1000"),
        risk_pct=Decimal("0.30"),
        entry_price=Decimal("100000"),
        stop_price=Decimal("99970"),
        max_leverage=Decimal("5"),
        half_risk_pct=Decimal("0.10"),
        constraints=CONSTRAINTS,
    )
    assert result.ok
    assert result.value is not None
    assert result.value.leverage <= Decimal("5")


def test_position_size_skips_when_effective_risk_too_small_after_cap() -> None:
    result = compute_position_size(
        equity_usd=Decimal("1000"),
        risk_pct=Decimal("0.30"),
        entry_price=Decimal("100000"),
        stop_price=Decimal("99999.5"),
        max_leverage=Decimal("1"),
        half_risk_pct=Decimal("0.10"),
        constraints=CONSTRAINTS,
    )
    assert not result.ok
    assert result.error == "effective_risk_below_half_risk"
