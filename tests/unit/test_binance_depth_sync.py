from __future__ import annotations

from marketdata.binance_depth_sync import BinanceDepthEventIds, BinanceDepthSync


def test_binance_sequence_validation_happy_path() -> None:
    sync = BinanceDepthSync()
    sync.seed_from_snapshot(snapshot_last_update_id=500)

    ok = sync.validate(
        BinanceDepthEventIds(first_update_id=501, final_update_id=510, previous_final_update_id=500)
    )
    assert ok.ok


def test_binance_sequence_gap_requires_resync() -> None:
    sync = BinanceDepthSync()
    sync.seed_from_snapshot(snapshot_last_update_id=500)

    failed = sync.validate(
        BinanceDepthEventIds(first_update_id=501, final_update_id=510, previous_final_update_id=499)
    )
    assert not failed.ok
    assert failed.error == "sequence_gap_resync_required"
