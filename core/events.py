from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core.enums import Direction, OrderStatus, RiskState, TakerSide, Venue


@dataclass(frozen=True, slots=True)
class TradeEvent:
    venue: Venue
    symbol: str
    price: Decimal
    qty: Decimal
    taker_side: TakerSide
    exchange_ts_ms: int
    recv_ts_ms: int
    canonical_ts_ms: int


@dataclass(frozen=True, slots=True)
class BookDeltaEvent:
    venue: Venue
    symbol: str
    bids: tuple[tuple[Decimal, Decimal], ...]
    asks: tuple[tuple[Decimal, Decimal], ...]
    is_snapshot: bool
    update_ids: tuple[int, ...]
    exchange_ts_ms: int
    recv_ts_ms: int
    canonical_ts_ms: int


@dataclass(frozen=True, slots=True)
class OrderEvent:
    venue: Venue
    symbol: str
    order_id: str
    status: OrderStatus
    side: Direction
    price: Decimal
    qty: Decimal
    filled_qty: Decimal
    avg_fill_price: Decimal
    reject_reason: str | None
    exchange_ts_ms: int
    recv_ts_ms: int
    canonical_ts_ms: int


@dataclass(frozen=True, slots=True)
class RiskSnapshot:
    equity: Decimal
    daily_pnl_pct: Decimal
    consecutive_losses: int
    cluster_exposure_r: Decimal
    risk_state: RiskState
