from __future__ import annotations

from pathlib import Path

from config.loader import load_app_config


def test_load_base_config() -> None:
    result = load_app_config(Path("config/base.yaml"))
    assert result.ok
    assert result.value is not None
    assert result.value.config_version == "2.0.0"
    assert result.value.system.symbols == ("BTCUSDT", "ETHUSDT", "SOLUSDT")
    assert result.value.hard_gates.min_score == 72
