from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core.result import Result
from core.types import InstrumentConstraints


@dataclass(frozen=True, slots=True)
class OrderDraft:
    symbol: str
    price: Decimal
    qty: Decimal


def validate_order(draft: OrderDraft, constraints: InstrumentConstraints) -> Result[None]:
    if draft.symbol != constraints.symbol:
        return Result(error="symbol_mismatch")
    if draft.price < constraints.min_price or draft.price > constraints.max_price:
        return Result(error="price_out_of_range")
    if draft.qty < constraints.min_qty or draft.qty > constraints.max_qty:
        return Result(error="qty_out_of_range")

    price_steps = draft.price / constraints.tick_size
    qty_steps = draft.qty / constraints.qty_step
    if price_steps != price_steps.to_integral_value():
        return Result(error="price_not_aligned_to_tick")
    if qty_steps != qty_steps.to_integral_value():
        return Result(error="qty_not_aligned_to_step")

    return Result(value=None)
