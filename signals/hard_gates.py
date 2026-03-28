from __future__ import annotations

from dataclasses import dataclass

from context.regime_engine import RegimeSnapshot, regime_allows_mean_reversion
from context.session_model import SessionModel
from features.feature_snapshot import MicrostructureFeatures


@dataclass(frozen=True, slots=True)
class HardGateReport:
    passed: bool
    details: dict[str, bool]


def evaluate_hard_gates(
    *,
    features: MicrostructureFeatures,
    regime: RegimeSnapshot,
    session_model: SessionModel,
    ts_ms: int,
    max_failure_ms: int,
    max_spread_pctl: float,
    min_depth_stability: float,
    min_data_quality: float,
    min_latency_score: float,
    min_followthrough_failure: float,
    min_absorption_or_exhaustion: float,
    max_signal_age_ms: int,
    min_gross_rr: float,
) -> HardGateReport:
    details = {
        "g1_session_active": session_model.is_active(ts_ms),
        "g2_regime_allowed": regime_allows_mean_reversion(regime),
        "g3_sweep_valid": (
            features.sweep_detected
            and features.sweep_penetration_ok
            and features.sweep_notional_ok
            and features.return_within_ms <= max_failure_ms
            and features.followthrough_failure_score >= min_followthrough_failure
        ),
        "g4_absorption_or_exhaustion": (
            max(features.absorption_score, features.exhaustion_score) >= min_absorption_or_exhaustion
        ),
        "g5_reversal": (features.obi_reversal_score > 0.0 and features.ofi_reversal_score > 0.0),
        "g6_market_quality": (
            features.spread_pctl <= max_spread_pctl
            and features.depth_stability_score >= min_depth_stability
            and features.data_quality_score >= min_data_quality
            and features.latency_score >= min_latency_score
        ),
        "g7_signal_fresh": features.signal_age_ms <= max_signal_age_ms,
        "g8_rr_positive": features.expected_rr >= min_gross_rr,
    }
    return HardGateReport(passed=all(details.values()), details=details)
