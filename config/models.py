from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SystemConfig:
    canonical_clock_ms: int
    symbols: tuple[str, ...]
    execution_venue: str
    data_venues: tuple[str, ...]
    ntp_max_offset_ms: int
    metadata_refresh_interval_h: int
    metadata_stale_threshold_h: int


@dataclass(frozen=True, slots=True)
class HardGatesConfig:
    min_score: int
    max_spread_pctl: int
    max_failure_ms: int
    min_data_quality_score: float
    min_latency_score: float
    max_signal_age_ms: int


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    passive_first: bool
    passive_ttl_ms: int
    passive_reprice_limit: int
    aggressive_fallback: bool
    aggressive_max_signal_age_ms: int
    aggressive_size_fraction: float


@dataclass(frozen=True, slots=True)
class RiskConfig:
    base_risk_pct: float
    high_score_risk_pct: float
    half_risk_pct: float
    daily_soft_stop_pct: float
    daily_hard_stop_pct: float
    max_leverage: int
    correlated_cluster_cap_r: float
    min_viable_risk_pct: float


@dataclass(frozen=True, slots=True)
class AppConfig:
    config_version: str
    system: SystemConfig
    hard_gates: HardGatesConfig
    execution: ExecutionConfig
    risk: RiskConfig
