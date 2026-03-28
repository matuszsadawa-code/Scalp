from __future__ import annotations

from dataclasses import dataclass

from context.regime_engine import RegimeSnapshot
from context.session_model import SessionModel
from features.feature_snapshot import MicrostructureFeatures
from signals.hard_gates import HardGateReport, evaluate_hard_gates
from signals.scorer import ScoreBreakdown, compute_score, risk_tier_from_score


@dataclass(frozen=True, slots=True)
class SignalDecision:
    should_trade: bool
    hard_gate_report: HardGateReport
    score: ScoreBreakdown
    risk_tier: str


def build_signal_decision(
    *,
    features: MicrostructureFeatures,
    regime: RegimeSnapshot,
    session_model: SessionModel,
    ts_ms: int,
) -> SignalDecision:
    gates = evaluate_hard_gates(
        features=features,
        regime=regime,
        session_model=session_model,
        ts_ms=ts_ms,
        max_failure_ms=3000,
        max_spread_pctl=80,
        min_depth_stability=0.60,
        min_data_quality=0.85,
        min_latency_score=0.80,
        min_followthrough_failure=0.5,
        min_absorption_or_exhaustion=0.5,
        max_signal_age_ms=2000,
        min_gross_rr=1.2,
    )
    score = compute_score(features)
    tier = risk_tier_from_score(score.total)
    return SignalDecision(
        should_trade=gates.passed and tier != "skip",
        hard_gate_report=gates,
        score=score,
        risk_tier=tier,
    )
