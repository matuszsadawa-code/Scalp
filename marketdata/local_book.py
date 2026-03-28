from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TypeAlias

from sortedcontainers import SortedDict

from core.events import BookDeltaEvent
from core.result import Result

BookLevels: TypeAlias = SortedDict[Decimal, Decimal]


@dataclass(slots=True)
class LocalBook:
    symbol: str
    bids: BookLevels = field(default_factory=SortedDict)
    asks: BookLevels = field(default_factory=SortedDict)
    is_valid: bool = False
    last_update_id: int | None = None

    def reset(self) -> None:
        self.bids.clear()
        self.asks.clear()
        self.is_valid = False
        self.last_update_id = None

    def apply_snapshot(self, event: BookDeltaEvent) -> Result[None]:
        self.reset()
        for price, size in event.bids:
            if size > Decimal("0"):
                self.bids[price] = size
        for price, size in event.asks:
            if size > Decimal("0"):
                self.asks[price] = size

        if event.update_ids:
            self.last_update_id = event.update_ids[-1]
        self.is_valid = bool(self.bids and self.asks)
        return Result(value=None)

    def apply_delta(self, event: BookDeltaEvent) -> Result[None]:
        if self.last_update_id is None and not self.is_valid:
            return Result(error="book_not_initialized")

        for price, size in event.bids:
            self._upsert(self.bids, price, size)
        for price, size in event.asks:
            self._upsert(self.asks, price, size)

        if event.update_ids:
            self.last_update_id = event.update_ids[-1]

        self.is_valid = bool(self.bids and self.asks and self.best_bid() < self.best_ask())
        if not self.is_valid:
            return Result(error="book_crossed_or_empty")
        return Result(value=None)

    def apply(self, event: BookDeltaEvent) -> Result[None]:
        if event.is_snapshot:
            return self.apply_snapshot(event)
        return self.apply_delta(event)

    def best_bid(self) -> Decimal:
        return self.bids.peekitem(-1)[0]

    def best_ask(self) -> Decimal:
        return self.asks.peekitem(0)[0]

    def _upsert(self, side: BookLevels, price: Decimal, size: Decimal) -> None:
        if size <= Decimal("0"):
            if price in side:
                del side[price]
            return
        side[price] = size
