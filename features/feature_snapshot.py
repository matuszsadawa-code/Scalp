from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MicrostructureFeatures:
    spread_pctl: float
    sweep_detected: bool
    sweep_penetration_ok: bool
    sweep_notional_ok: bool
    return_within_ms: int
    followthrough_failure_score: float
    absorption_score: float
    exhaustion_score: float
    obi_reversal_score: float
    ofi_reversal_score: float
    depth_stability_score: float
    data_quality_score: float
    latency_score: float
    fair_value_gap_bps: float
    expected_rr: float
    signal_age_ms: int
