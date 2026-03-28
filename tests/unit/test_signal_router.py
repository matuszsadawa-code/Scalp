from __future__ import annotations

from datetime import datetime, timezone

from context.regime_engine import RegimeSnapshot
from context.session_model import default_session_model
from features.feature_snapshot import MicrostructureFeatures
from signals.signal_router import build_signal_decision


def _active_ts_ms() -> int:
    return int(datetime(2026, 3, 27, 9, 0, tzinfo=timezone.utc).timestamp() * 1000)


def test_signal_decision_trades_when_all_gates_and_score_pass() -> None:
    features = MicrostructureFeatures(
        spread_pctl=20.0,
        sweep_detected=True,
        sweep_penetration_ok=True,
        sweep_notional_ok=True,
        return_within_ms=1200,
        followthrough_failure_score=0.9,
        absorption_score=0.8,
        exhaustion_score=0.3,
        obi_reversal_score=0.9,
        ofi_reversal_score=0.8,
        depth_stability_score=0.9,
        data_quality_score=0.95,
        latency_score=0.95,
        fair_value_gap_bps=12.0,
        expected_rr=1.8,
        signal_age_ms=400,
    )
    decision = build_signal_decision(
        features=features,
        regime=RegimeSnapshot(name="balanced", confidence=0.9),
        session_model=default_session_model(),
        ts_ms=_active_ts_ms(),
    )
    assert decision.hard_gate_report.passed
    assert decision.score.total >= 72.0
    assert decision.should_trade


def test_signal_decision_skips_when_gate_fails_even_if_score_high() -> None:
    features = MicrostructureFeatures(
        spread_pctl=20.0,
        sweep_detected=True,
        sweep_penetration_ok=True,
        sweep_notional_ok=True,
        return_within_ms=1200,
        followthrough_failure_score=0.9,
        absorption_score=0.9,
        exhaustion_score=0.9,
        obi_reversal_score=0.9,
        ofi_reversal_score=0.9,
        depth_stability_score=0.95,
        data_quality_score=0.97,
        latency_score=0.97,
        fair_value_gap_bps=20.0,
        expected_rr=2.0,
        signal_age_ms=2500,
    )
    decision = build_signal_decision(
        features=features,
        regime=RegimeSnapshot(name="balanced", confidence=0.9),
        session_model=default_session_model(),
        ts_ms=_active_ts_ms(),
    )
    assert not decision.hard_gate_report.details["g7_signal_fresh"]
    assert decision.score.total >= 72.0
    assert not decision.should_trade
