from __future__ import annotations

from pathlib import Path

import yaml

from config.models import AppConfig, ExecutionConfig, HardGatesConfig, RiskConfig, SystemConfig
from core.result import Result


def _read_yaml(path: Path) -> Result[dict[str, object]]:
    if not path.exists():
        return Result(error=f"missing config file: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except Exception as exc:  # noqa: BLE001
        return Result(error=f"cannot read yaml {path}: {exc}")

    if not isinstance(payload, dict):
        return Result(error=f"config root must be object: {path}")
    return Result(value=payload)


def load_app_config(path: Path) -> Result[AppConfig]:
    raw_result = _read_yaml(path)
    if not raw_result.ok:
        return Result(error=raw_result.error)
    assert raw_result.value is not None
    raw = raw_result.value

    try:
        system_raw = raw["system"]
        hard_gates_raw = raw["hard_gates"]
        execution_raw = raw["execution"]
        risk_raw = raw["risk"]
        if not isinstance(system_raw, dict):
            return Result(error="system section must be an object")
        if not isinstance(hard_gates_raw, dict):
            return Result(error="hard_gates section must be an object")
        if not isinstance(execution_raw, dict):
            return Result(error="execution section must be an object")
        if not isinstance(risk_raw, dict):
            return Result(error="risk section must be an object")

        config = AppConfig(
            config_version=str(raw["config_version"]),
            system=SystemConfig(
                canonical_clock_ms=int(system_raw["canonical_clock_ms"]),
                symbols=tuple(str(item) for item in system_raw["symbols"]),
                execution_venue=str(system_raw["execution_venue"]),
                data_venues=tuple(str(item) for item in system_raw["data_venues"]),
                ntp_max_offset_ms=int(system_raw["ntp_max_offset_ms"]),
                metadata_refresh_interval_h=int(system_raw["metadata_refresh_interval_h"]),
                metadata_stale_threshold_h=int(system_raw["metadata_stale_threshold_h"]),
            ),
            hard_gates=HardGatesConfig(
                min_score=int(hard_gates_raw["min_score"]),
                max_spread_pctl=int(hard_gates_raw["max_spread_pctl"]),
                max_failure_ms=int(hard_gates_raw["max_failure_ms"]),
                min_data_quality_score=float(hard_gates_raw["min_data_quality_score"]),
                min_latency_score=float(hard_gates_raw["min_latency_score"]),
                max_signal_age_ms=int(hard_gates_raw["max_signal_age_ms"]),
            ),
            execution=ExecutionConfig(
                passive_first=bool(execution_raw["passive_first"]),
                passive_ttl_ms=int(execution_raw["passive_ttl_ms"]),
                passive_reprice_limit=int(execution_raw["passive_reprice_limit"]),
                aggressive_fallback=bool(execution_raw["aggressive_fallback"]),
                aggressive_max_signal_age_ms=int(execution_raw["aggressive_max_signal_age_ms"]),
                aggressive_size_fraction=float(execution_raw["aggressive_size_fraction"]),
            ),
            risk=RiskConfig(
                base_risk_pct=float(risk_raw["base_risk_pct"]),
                high_score_risk_pct=float(risk_raw["high_score_risk_pct"]),
                half_risk_pct=float(risk_raw["half_risk_pct"]),
                daily_soft_stop_pct=float(risk_raw["daily_soft_stop_pct"]),
                daily_hard_stop_pct=float(risk_raw["daily_hard_stop_pct"]),
                max_leverage=int(risk_raw["max_leverage"]),
                correlated_cluster_cap_r=float(risk_raw["correlated_cluster_cap_r"]),
                min_viable_risk_pct=float(risk_raw["min_viable_risk_pct"]),
            ),
        )
        return Result(value=config)
    except KeyError as exc:
        return Result(error=f"missing required config key: {exc}")
    except (TypeError, ValueError) as exc:
        return Result(error=f"invalid config value type: {exc}")
