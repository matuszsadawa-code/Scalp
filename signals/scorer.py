from __future__ import annotations

from dataclasses import dataclass

from features.feature_snapshot import MicrostructureFeatures


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    total: float
    components: dict[str, float]


def compute_score(features: MicrostructureFeatures) -> ScoreBreakdown:
    components = {
        "sweep_quality": 18.0 if features.sweep_detected and features.sweep_penetration_ok else 0.0,
        "return_failure_quality": 18.0 * min(1.0, features.followthrough_failure_score),
        "absorption_exhaustion": 16.0 * min(1.0, max(features.absorption_score, features.exhaustion_score)),
        "obi_ofi_reversal": 14.0 * min(1.0, (features.obi_reversal_score + features.ofi_reversal_score) / 2.0),
        "fair_value": 10.0 * min(1.0, max(0.0, features.fair_value_gap_bps / 10.0)),
        "market_quality": 6.0 * min(1.0, (features.data_quality_score + features.latency_score) / 2.0),
        "depth_stability": 8.0 * min(1.0, features.depth_stability_score),
    }
    total = float(sum(components.values()))
    return ScoreBreakdown(total=total, components=components)


def risk_tier_from_score(score: float) -> str:
    if score < 72.0:
        return "skip"
    if score < 80.0:
        return "half"
    if score < 88.0:
        return "base"
    return "max"
