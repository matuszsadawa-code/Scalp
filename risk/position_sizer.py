from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from core.result import Result
from core.types import InstrumentConstraints


@dataclass(frozen=True, slots=True)
class PositionSizeResult:
    qty: Decimal
    notional: Decimal
    leverage: Decimal
    effective_risk_usd: Decimal


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= Decimal("0"):
        raise ValueError("qty step must be positive")
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def compute_position_size(
    *,
    equity_usd: Decimal,
    risk_pct: Decimal,
    entry_price: Decimal,
    stop_price: Decimal,
    max_leverage: Decimal,
    half_risk_pct: Decimal,
    constraints: InstrumentConstraints,
) -> Result[PositionSizeResult]:
    if entry_price <= Decimal("0"):
        return Result(error="invalid_entry_price")
    stop_distance = abs(entry_price - stop_price)
    if stop_distance <= Decimal("0"):
        return Result(error="invalid_stop_distance")

    risk_usd = equity_usd * risk_pct / Decimal("100")
    raw_qty = risk_usd / stop_distance
    qty = _floor_to_step(raw_qty, constraints.qty_step)

    max_qty_by_leverage = _floor_to_step((equity_usd * max_leverage) / entry_price, constraints.qty_step)
    if qty > max_qty_by_leverage:
        qty = max_qty_by_leverage

    if qty < constraints.min_qty:
        return Result(error="qty_below_min")

    qty = min(qty, constraints.max_qty)
    notional = qty * entry_price
    leverage = notional / equity_usd if equity_usd > Decimal("0") else Decimal("0")
    effective_risk_usd = qty * stop_distance

    min_viable_risk_usd = equity_usd * half_risk_pct / Decimal("100")
    if effective_risk_usd < min_viable_risk_usd:
        return Result(error="effective_risk_below_half_risk")

    return Result(
        value=PositionSizeResult(
            qty=qty,
            notional=notional,
            leverage=leverage,
            effective_risk_usd=effective_risk_usd,
        )
    )
