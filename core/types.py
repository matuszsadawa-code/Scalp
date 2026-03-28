from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal, getcontext

getcontext().prec = 18
getcontext().rounding = ROUND_DOWN

Symbol = str
Price = Decimal
Qty = Decimal
TimestampMs = int


@dataclass(frozen=True, slots=True)
class InstrumentConstraints:
    symbol: Symbol
    tick_size: Decimal
    qty_step: Decimal
    min_qty: Decimal
    max_qty: Decimal
    min_price: Decimal
    max_price: Decimal
