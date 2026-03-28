from __future__ import annotations

from decimal import Decimal

from core.types import InstrumentConstraints
from execution.order_validator import OrderDraft, validate_order


def test_order_validator_accepts_aligned_order() -> None:
    constraints = InstrumentConstraints(
        symbol="ETHUSDT",
        tick_size=Decimal("0.01"),
        qty_step=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        max_qty=Decimal("1000"),
        min_price=Decimal("1"),
        max_price=Decimal("100000"),
    )
    result = validate_order(
        OrderDraft(symbol="ETHUSDT", price=Decimal("2500.12"), qty=Decimal("0.125")),
        constraints,
    )
    assert result.ok


def test_order_validator_rejects_tick_misalignment() -> None:
    constraints = InstrumentConstraints(
        symbol="ETHUSDT",
        tick_size=Decimal("0.10"),
        qty_step=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        max_qty=Decimal("1000"),
        min_price=Decimal("1"),
        max_price=Decimal("100000"),
    )
    result = validate_order(
        OrderDraft(symbol="ETHUSDT", price=Decimal("2500.12"), qty=Decimal("0.125")),
        constraints,
    )
    assert not result.ok
    assert result.error == "price_not_aligned_to_tick"
