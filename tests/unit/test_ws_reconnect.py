from __future__ import annotations

from marketdata.ws_reconnect import ReconnectBackoff, ReconnectPolicy


def test_reconnect_backoff_grows_and_caps() -> None:
    backoff = ReconnectBackoff(
        ReconnectPolicy(
            initial_delay_s=1.0,
            max_delay_s=8.0,
            backoff_multiplier=2.0,
            jitter_max_ms=0,
        )
    )

    delays = [backoff.next_delay_s() for _ in range(5)]
    assert delays == [1.0, 2.0, 4.0, 8.0, 8.0]
