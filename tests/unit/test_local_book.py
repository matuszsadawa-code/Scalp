from __future__ import annotations

from decimal import Decimal

from core.enums import Venue
from core.events import BookDeltaEvent
from marketdata.local_book import LocalBook


def _event(*, snapshot: bool, bids: tuple[tuple[str, str], ...], asks: tuple[tuple[str, str], ...]) -> BookDeltaEvent:
    return BookDeltaEvent(
        venue=Venue.BYBIT,
        symbol="BTCUSDT",
        bids=tuple((Decimal(p), Decimal(q)) for p, q in bids),
        asks=tuple((Decimal(p), Decimal(q)) for p, q in asks),
        is_snapshot=snapshot,
        update_ids=(100, 101),
        exchange_ts_ms=1,
        recv_ts_ms=2,
        canonical_ts_ms=0,
    )


def test_snapshot_and_delta_updates_book() -> None:
    book = LocalBook(symbol="BTCUSDT")
    snap = _event(snapshot=True, bids=(("100", "1"),), asks=(("101", "2"),))
    assert book.apply(snap).ok
    assert book.is_valid

    delta = _event(snapshot=False, bids=(("100", "0"), ("99", "3")), asks=(("102", "1"),))
    assert book.apply(delta).ok
    assert book.best_bid() == Decimal("99")
    assert book.best_ask() == Decimal("101")


def test_crossed_book_invalidates_entries() -> None:
    book = LocalBook(symbol="BTCUSDT")
    snap = _event(snapshot=True, bids=(("100", "1"),), asks=(("101", "1"),))
    assert book.apply(snap).ok

    crossed = _event(snapshot=False, bids=(("103", "1"),), asks=())
    result = book.apply(crossed)
    assert not result.ok
    assert result.error == "book_crossed_or_empty"
    assert not book.is_valid
