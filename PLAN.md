# VOLF HYPER APEX 2026 — PLAN IMPLEMENTACJI

## Kompletny przewodnik budowy systemu

**Wersja:** `impl-plan-1.0.0`
**Blueprint reference:** `blueprint-2.0.0`
**Data:** 2026-03-28

-----

## Spis treści

1. [Tech stack i środowisko](#1-tech-stack-i-środowisko)
1. [Konwencje projektowe](#2-konwencje-projektowe)
1. [Graf zależności modułów](#3-graf-zależności-modułów)
1. [Faza 0 — Projekt i scaffolding](#4-faza-0--projekt-i-scaffolding)
1. [Faza 1 — Infrastructure](#5-faza-1--infrastructure)
1. [Faza 2 — Context](#6-faza-2--context)
1. [Faza 3 — Features](#7-faza-3--features)
1. [Faza 4 — Signals](#8-faza-4--signals)
1. [Faza 5 — Execution](#9-faza-5--execution)
1. [Faza 6 — Risk](#10-faza-6--risk)
1. [Faza 7 — Replay & Validation](#11-faza-7--replay--validation)
1. [Faza 8 — Demo Forward](#12-faza-8--demo-forward)
1. [Cross-cutting concerns](#13-cross-cutting-concerns)
1. [Acceptance gates między fazami](#14-acceptance-gates-między-fazami)
1. [Checklist końcowy](#15-checklist-końcowy)

-----

## 1. Tech stack i środowisko

### 1.1 Język i runtime

- Python 3.12+ (wymagane: `match` statements, `type` union syntax `X | Y`, performance improvements).
- Typowanie: `mypy --strict` na całym codebase. Zero `Any` w publicznych interfejsach.
- Dataclass’y: `@dataclass(slots=True, frozen=True)` dla immutable event/state objects. Mutable state objects używają `slots=True` bez `frozen`.

### 1.2 Zależności core

|Paczka            |Cel                                             |Wersja (min)|
|------------------|------------------------------------------------|------------|
|`aiohttp`         |Async HTTP (REST calls do Bybit/Binance)        |3.9+        |
|`websockets`      |WebSocket connections                           |12.0+       |
|`orjson`          |Szybki JSON parser (venue messages)             |3.9+        |
|`pyarrow`         |Parquet read/write (storage layer)              |15.0+       |
|`pyyaml`          |Config loading                                  |6.0+        |
|`ntplib`          |NTP sync check                                  |0.4+        |
|`numpy`           |Rolling windows, statistics, z-scores           |1.26+       |
|`sortedcontainers`|Sorted orderbook levels (O(log n) insert/delete)|2.4+        |
|`structlog`       |Structured JSON logging                         |24.0+       |
|`uvloop`          |High-performance event loop (Linux)             |0.19+       |

### 1.3 Zależności dev/test

|Paczka                     |Cel                                                 |
|---------------------------|----------------------------------------------------|
|`pytest` + `pytest-asyncio`|Testing async code                                  |
|`pytest-cov`               |Coverage                                            |
|`mypy`                     |Static type checking                                |
|`ruff`                     |Linting + formatting                                |
|`hypothesis`               |Property-based testing (book reconstruction, sizing)|
|`freezegun`                |Time mocking                                        |

### 1.4 Zależności opcjonalne (monitoring)

|Paczka              |Cel                          |
|--------------------|-----------------------------|
|`prometheus-client` |Metrics export               |
|`grafana` (external)|Dashboard visualization      |
|`rich`              |Terminal dashboard (dev mode)|

### 1.5 Środowisko operacyjne

- OS: Linux (Ubuntu 22.04+ / Debian 12+). `uvloop` wymaga Linux.
- RAM: min 4 GB (book state + rolling windows + parquet buffers).
- Disk: min 50 GB SSD (raw event logging at ~2 GB/day for 3 symbols).
- Network: stable connection, < 100 ms latency to Bybit/Binance APIs.
- Python venv: izolowany virtualenv per deployment.

### 1.6 Decimal context

```python
# core/types.py — global Decimal context
import decimal
decimal.getcontext().prec = 18
decimal.getcontext().rounding = decimal.ROUND_DOWN  # always round qty DOWN
```

-----

## 2. Konwencje projektowe

### 2.1 Naming

- Pliki: `snake_case.py`
- Klasy: `PascalCase`
- Stałe: `UPPER_SNAKE_CASE`
- Metody publiczne: `snake_case`
- Metody prywatne: `_snake_case`
- Type aliases: `PascalCase` (np. `Price = Decimal`, `Qty = Decimal`)

### 2.2 Error handling

- Warstwa WS/REST: `try/except` z explicit retry logic. Nigdy nie swallow exceptions bez logowania.
- Warstwa logiki: zwracanie `Result[T, Error]` pattern (dataclass z `value` i `error`). Żadne exception-based flow control w hot path.
- KILL_SWITCH: odpalany tylko przez dedicated `kill_switch.py` — żaden inny moduł nie wywołuje `sys.exit()`.

### 2.3 Async architecture

- Jeden główny `asyncio` event loop (z `uvloop`).
- Każdy WS connection = osobny `asyncio.Task`.
- Canonical clock = `asyncio.Task` z `asyncio.sleep` (100 ms ticks).
- REST polling (funding/OI, metadata, venue status) = osobne `asyncio.Task` z własnymi interwałami.
- Shared state: mutable state objects chronione przez pattern „single writer, multiple readers”. Brak explicit locks — zamiast tego architektura single-threaded async.
- Inter-module communication: direct method calls (nie message queues) — system jest single-process.

### 2.4 Config loading

- Wszystkie YAML config files ładowane na boot do frozen dataclass’ów.
- Config jest immutable po boot. Zmiana wymaga restartu.
- `config_version` jest walidowane — mismatch = abort boot.
- Config snapshot (pełny dump) logowany przy każdym boot.

### 2.5 Testowanie

- Unit testy: każdy moduł ma odpowiadający `tests/test_<module>.py`.
- Integration testy: per-phase, testują współdziałanie modułów w danej fazie.
- Property-based testy: book reconstruction, position sizing, score normalization.
- Replay testy: od Fazy 7 — identyczne wyniki z recorded events.

### 2.6 Git workflow

- Branch per faza: `phase-1/infrastructure`, `phase-2/context`, itd.
- PR per moduł lub per logiczna grupa plików.
- Merge do `main` dopiero po przejściu acceptance gate danej fazy.
- Tagi: `v0.1.0` (phase 1 done), `v0.2.0` (phase 2), itd.

-----

## 3. Graf zależności modułów

```
core/
  ├── enums.py          ← zero dependencies
  ├── types.py          ← enums
  ├── events.py         ← types, enums
  ├── clocks.py         ← types
  ├── ids.py            ← zero dependencies
  ├── math.py           ← types
  └── state.py          ← types, enums, events

config/                 ← core/types, core/enums
  ├── base.yaml
  ├── symbols.yaml
  ├── sessions.yaml
  ├── execution.yaml
  ├── risk.yaml
  └── venues.yaml

boot/                   ← core, config
  ├── instrument_loader.py    ← core/types, aiohttp
  ├── environment_check.py    ← zero runtime deps
  ├── venue_health.py         ← aiohttp, core/types
  ├── ntp_sync.py             ← ntplib, core/clocks
  └── startup_validator.py    ← boot/*, core/state

marketdata/             ← core, config, boot
  ├── bybit_public_ws.py      ← websockets, core/events, ws_reconnect
  ├── bybit_private_ws.py     ← websockets, core/events, ws_reconnect
  ├── binance_ws.py           ← websockets, core/events, ws_reconnect
  ├── snapshot_fetcher.py     ← aiohttp, core/events
  ├── normalizer.py           ← core/events, core/types
  ├── local_book.py           ← core/events, core/types, sortedcontainers
  ├── resync_manager.py       ← local_book, snapshot_fetcher
  ├── ws_reconnect.py         ← websockets, core/clocks
  └── canonical_clock.py      ← core/clocks, core/state

storage/                ← core
  ├── raw_writer.py           ← pyarrow, core/events
  ├── parquet_store.py        ← pyarrow
  ├── feature_store.py        ← pyarrow, core/types
  ├── order_log.py            ← core/events, structlog
  └── trade_log.py            ← core/events, structlog

context/                ← core, marketdata, config
  ├── session_model.py        ← config/sessions, core/clocks
  ├── value_profile.py        ← core/types, numpy
  ├── vwap_engine.py          ← core/types, core/events
  ├── regime_engine.py        ← value_profile, volatility_filters, core/types
  ├── volatility_filters.py   ← core/events, numpy
  ├── funding_oi_context.py   ← aiohttp, core/types, numpy
  └── level_map.py            ← value_profile, core/types

features/               ← core, marketdata, context
  ├── obi.py                  ← marketdata/local_book, core/types
  ├── ofi.py                  ← marketdata/local_book, core/types, numpy
  ├── microprice.py           ← marketdata/local_book, core/types
  ├── cvd.py                  ← core/events, numpy
  ├── lad.py                  ← core/events, numpy
  ├── sweep_detector.py       ← context/level_map, core/events, numpy
  ├── absorption.py           ← core/events, marketdata/local_book
  ├── exhaustion.py           ← core/events, numpy
  ├── replenishment.py        ← marketdata/local_book, numpy
  ├── spoof_probability.py    ← marketdata/local_book, numpy
  ├── iceberg_inference.py    ← core/events, marketdata/local_book
  ├── liquidation_burst.py    ← core/events, numpy
  ├── trade_efficiency.py     ← core/events, numpy
  └── feature_snapshot.py     ← ALL features/*, core/types

signals/                ← core, features, context, config
  ├── hard_gates.py           ← features/feature_snapshot, context/*, config
  ├── score_normalizer.py     ← core/types
  ├── scorer.py               ← score_normalizer, config
  ├── long_setup.py           ← features/*, context/*
  ├── short_setup.py          ← features/*, context/*
  └── signal_router.py        ← hard_gates, scorer, long_setup, short_setup

execution/              ← core, signals, marketdata, config
  ├── order_validator.py      ← boot/instrument_loader, core/types
  ├── order_router.py         ← marketdata/bybit_private_ws, order_validator
  ├── stale_signal_guard.py   ← core/clocks, config
  ├── fill_tracker.py         ← core/events
  ├── sl_tp_manager.py        ← core/types, context/*, config
  ├── execution_fsm.py        ← ALL execution/*, signals/signal_router
  └── venue_constraints.py    ← boot/instrument_loader

risk/                   ← core, execution, config
  ├── position_sizer.py       ← boot/instrument_loader, core/types, config
  ├── correlation_bucket.py   ← core/types
  ├── daily_limits.py         ← core/types, config
  ├── degraded_mode.py        ← marketdata/*, core/state
  ├── kill_switch.py          ← core/state, shutdown/graceful_shutdown
  ├── risk_fsm.py             ← ALL risk/*, config
  └── risk_engine.py          ← risk_fsm, position_sizer, correlation_bucket

monitoring/             ← core, marketdata, execution, risk
  ├── dashboard.py            ← ALL state objects
  ├── health.py               ← marketdata/*, core/clocks
  ├── latency.py              ← core/events, numpy
  ├── alerts.py               ← risk/*, monitoring/health
  ├── venue_status.py         ← aiohttp, core/types
  └── system_status.py        ← ALL monitoring/*

shutdown/               ← core, execution, marketdata, storage
  └── graceful_shutdown.py    ← execution/*, marketdata/*, storage/*

replay/                 ← core, ALL layers
  ├── event_replay.py         ← storage/*, core/events
  ├── book_replay.py          ← marketdata/local_book, storage/*
  ├── fill_simulator.py       ← core/types, config
  ├── walk_forward.py         ← replay/*, signals/*, execution/*
  └── metrics.py              ← core/types, numpy

app.py                  ← boot/*, ALL layers
```

-----

## 4. Faza 0 — Projekt i scaffolding

### 4.0.1 Cel

Przygotowanie repozytorium, config structure, core types i convention enforcement.

### 4.0.2 Zadania

**Z1: Inicjalizacja repozytorium**

```bash
mkdir -p volf_hyper_apex/{config,core,boot,marketdata,context,features,signals,execution,risk,storage,replay,monitoring,shutdown}
mkdir -p tests/{unit,integration,property}
touch volf_hyper_apex/__init__.py
touch volf_hyper_apex/{core,boot,marketdata,context,features,signals,execution,risk,storage,replay,monitoring,shutdown}/__init__.py
```

**Z2: Tooling setup**

- `pyproject.toml` z definicją projektu, dependencies, tool configs.
- `.python-version` = `3.12`
- `ruff.toml` — linting rules.
- `mypy.ini` — `strict = true`.
- `pytest.ini` — async mode = auto.
- `.gitignore` — standardowy Python + `.env`, `data/`, `logs/`.
- `Makefile` — targets: `lint`, `type-check`, `test`, `test-cov`, `format`, `all-checks`.

**Z3: `core/enums.py`**

```python
from enum import StrEnum, auto

class Venue(StrEnum):
    BYBIT = "bybit"
    BINANCE = "binance"

class TakerSide(StrEnum):
    BUY = "buy"
    SELL = "sell"

class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"

class SessionName(StrEnum):
    EU_OPEN = "EU_OPEN"
    US_OVERLAP = "US_OVERLAP"
    FUNDING_ADJACENT = "FUNDING_ADJACENT"
    INACTIVE = "INACTIVE"

class RegimeName(StrEnum):
    BALANCED = "BALANCED"
    ROTATIONAL = "ROTATIONAL"
    LOCAL_STRETCH = "LOCAL_STRETCH"
    TREND_DAY = "TREND_DAY"
    VOL_EXPANSION = "VOL_EXPANSION"
    INVALID = "INVALID"

class RiskState(StrEnum):
    NORMAL = "NORMAL"
    REDUCED = "REDUCED"
    PAUSED_SETUP = "PAUSED_SETUP"
    PAUSED_STRATEGY = "PAUSED_STRATEGY"
    KILL_SWITCH = "KILL_SWITCH"

class ExecutionState(StrEnum):
    IDLE = "IDLE"
    WATCHING = "WATCHING"
    ARMED = "ARMED"
    SUBMIT_PASSIVE = "SUBMIT_PASSIVE"
    WAIT_PASSIVE_ACK = "WAIT_PASSIVE_ACK"
    WAIT_PASSIVE_FILL = "WAIT_PASSIVE_FILL"
    PASSIVE_REPRICE = "PASSIVE_REPRICE"
    SUBMIT_AGGRESSIVE = "SUBMIT_AGGRESSIVE"
    WAIT_AGGRESSIVE_ACK = "WAIT_AGGRESSIVE_ACK"
    WAIT_FILL = "WAIT_FILL"
    POSITION_OPEN = "POSITION_OPEN"
    MANAGE_EXIT = "MANAGE_EXIT"
    PARTIAL_EXIT = "PARTIAL_EXIT"
    CLOSE_POSITION = "CLOSE_POSITION"
    ABORTED = "ABORTED"
    ERROR = "ERROR"

class VenueHealthState(StrEnum):
    FULLY_OPERATIONAL = "FULLY_OPERATIONAL"
    BYBIT_PUBLIC_DEGRADED = "BYBIT_PUBLIC_DEGRADED"
    BINANCE_DEGRADED = "BINANCE_DEGRADED"
    PRIVATE_WS_DEGRADED = "PRIVATE_WS_DEGRADED"
    BOOK_INVALID = "BOOK_INVALID"
    METADATA_STALE = "METADATA_STALE"
    SYSTEM_ABNORMAL = "SYSTEM_ABNORMAL"

class OrderStatus(StrEnum):
    NEW = "New"
    PARTIALLY_FILLED = "PartiallyFilled"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"
    DEACTIVATED = "Deactivated"

class SweepLevelType(StrEnum):
    PRIOR_HIGH = "prior_high"
    PRIOR_LOW = "prior_low"
    VAH = "vah"
    VAL = "val"
    POC = "poc"
    LVN_EDGE = "lvn_edge"
    FAILED_AUCTION = "failed_auction"

class EntryStyle(StrEnum):
    PASSIVE_FIRST = "passive_first"
    AGGRESSIVE_CONFIRM = "aggressive_confirm"
    SKIP = "skip"
```

**Z4: `core/types.py`**

```python
import decimal
from decimal import Decimal
from typing import TypeAlias

decimal.getcontext().prec = 18
decimal.getcontext().rounding = decimal.ROUND_DOWN

Price: TypeAlias = Decimal
Qty: TypeAlias = Decimal
Notional: TypeAlias = Decimal
Timestamp: TypeAlias = int       # milliseconds
Bps: TypeAlias = float
Score: TypeAlias = float         # 0.0–1.0 normalized

ZERO_PRICE = Decimal("0")
ZERO_QTY = Decimal("0")

def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Floor value to nearest step increment."""
    return (value // step) * step

def round_to_tick(price: Decimal, tick_size: Decimal) -> Decimal:
    """Round price to nearest tick."""
    return (price / tick_size).to_integral_value(rounding=decimal.ROUND_HALF_UP) * tick_size
```

**Z5: `core/events.py`**

Implementacja wszystkich event dataclass’ów z sekcji 10.1 blueprintu. Frozen, slotted.

**Z6: `core/clocks.py`**

```python
import time

def monotonic_ms() -> int:
    """Monotonic clock in milliseconds. Used for recv_ts_ms."""
    return int(time.monotonic_ns() // 1_000_000)

def utc_ms() -> int:
    """UTC wall clock in milliseconds."""
    return int(time.time() * 1000)

def to_canonical_bucket(recv_ts_ms: int, bucket_size_ms: int = 100) -> int:
    """Assign recv_ts_ms to nearest canonical bucket."""
    return (recv_ts_ms // bucket_size_ms) * bucket_size_ms
```

**Z7: `core/ids.py`**

```python
import uuid

def generate_order_link_id() -> str:
    """Generate unique order link ID for Bybit."""
    return f"volf_{uuid.uuid4().hex[:16]}"

def generate_signal_id() -> str:
    return f"sig_{uuid.uuid4().hex[:12]}"
```

**Z8: `core/math.py`**

Rolling window helpers, z-score, percentile, CV — pure numpy-based, stateless functions.

```python
import numpy as np
from numpy.typing import NDArray

def rolling_zscore(values: NDArray[np.float64], new_value: float) -> float: ...
def rolling_percentile(values: NDArray[np.float64], new_value: float) -> float: ...
def coefficient_of_variation(values: NDArray[np.float64]) -> float: ...
def exponential_weighted_mean(values: NDArray[np.float64], alpha: float) -> float: ...
```

**Z9: `core/state.py`**

Global system state container — mutable singleton, holds references to all live state.

**Z10: Config dataclass’y**

Stworzenie frozen dataclass’ów mapujących każdą sekcję YAML config (sekcja 27 blueprintu):

- `SystemConfig`
- `SessionWindowConfig`, `SessionsConfig`
- `RegimeConfig`
- `HardGatesConfig`
- `ExecutionConfig`
- `RiskConfig`
- `ExitConfig`
- `WebSocketConfig`
- `MonitoringConfig`
- `AppConfig` (top-level, zawiera wszystkie powyższe)

Config loader: `load_config(path: str) -> AppConfig` — waliduje `config_version`, parsuje YAML, zwraca frozen `AppConfig`.

### 4.0.3 Acceptance gate

- `make all-checks` passes (lint, type-check, test).
- Wszystkie core types importowalne i type-safe.
- Config loader poprawnie parsuje example YAML.
- 100% coverage na `core/`.

-----

## 5. Faza 1 — Infrastructure

### 5.1 Cel

Działający pipeline: boot → WS connections → raw event capture → local book → raw logging. Zero logiki tradingowej. System startuje, łączy się, odbiera dane, buduje book, loguje, i potrafi się zamknąć gracefully.

### 5.1.1 Kolejność implementacji

```
boot/ntp_sync.py
boot/environment_check.py
boot/instrument_loader.py
boot/venue_health.py
boot/startup_validator.py
marketdata/ws_reconnect.py
marketdata/bybit_public_ws.py
marketdata/binance_ws.py
marketdata/bybit_private_ws.py
marketdata/snapshot_fetcher.py
marketdata/normalizer.py
marketdata/local_book.py
marketdata/resync_manager.py
marketdata/canonical_clock.py
storage/raw_writer.py
storage/parquet_store.py
monitoring/health.py
monitoring/latency.py
monitoring/venue_status.py
shutdown/graceful_shutdown.py
app.py (skeleton)
```

-----

### 5.2 `boot/ntp_sync.py`

**Cel:** Walidacja synchronizacji zegara systemowego z NTP.

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class NtpCheckResult:
    offset_ms: float
    server: str
    is_acceptable: bool
    checked_at_ms: int

class NtpSyncChecker:
    def __init__(self, max_offset_ms: float = 2000.0, servers: list[str] | None = None): ...
    async def check(self) -> NtpCheckResult: ...
    async def check_or_abort(self) -> NtpCheckResult:
        """Check NTP; raise SystemExit if offset > max.""" ...
```

**Logika:**

1. Query NTP server (default: `pool.ntp.org`, fallback: `time.google.com`).
1. Oblicz offset w ms.
1. Jeśli `abs(offset) > max_offset_ms` → `is_acceptable = False`.
1. W `check_or_abort`: jeśli nie acceptable → log CRITICAL + raise `SystemExit`.

**Periodic task:** Co 300 s (config `ntp_check_interval_s`) re-check. Jeśli drift > 2000 ms → trigger KILL_SWITCH via `core/state.py` flag.

**Testy:**

- Mock `ntplib.NTPClient` — test acceptable/unacceptable offsets.
- Test `check_or_abort` raises on bad offset.

-----

### 5.3 `boot/environment_check.py`

**Cel:** Walidacja środowiska przed startem.

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class EnvironmentCheckResult:
    python_version_ok: bool
    disk_space_ok: bool
    disk_free_gb: float
    required_packages_ok: bool
    missing_packages: list[str]
    all_ok: bool

def check_environment() -> EnvironmentCheckResult: ...
```

**Logika:**

1. Check Python >= 3.12.
1. Check disk space >= 10 GB free na partycji z `data/` i `logs/`.
1. Check critical imports: `aiohttp`, `websockets`, `orjson`, `pyarrow`, `numpy`, `sortedcontainers`.

**Testy:**

- Mock `sys.version_info`, `shutil.disk_usage`.

-----

### 5.4 `boot/instrument_loader.py`

**Cel:** Pobranie i cache’owanie instrument metadata z Bybit REST API.

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class InstrumentMeta:
    symbol: str
    tick_size: Decimal
    min_price: Decimal
    max_price: Decimal
    qty_step: Decimal
    min_order_qty: Decimal
    max_order_qty: Decimal
    max_mkt_order_qty: Decimal
    price_scale: int
    min_leverage: Decimal
    max_leverage: Decimal
    leverage_step: Decimal

class InstrumentLoader:
    def __init__(self, base_url: str, symbols: list[str]): ...
    async def load_all(self) -> dict[str, InstrumentMeta]: ...
    async def refresh(self) -> dict[str, InstrumentMeta]: ...
    def get(self, symbol: str) -> InstrumentMeta: ...
    def is_stale(self, threshold_hours: float = 8.0) -> bool: ...
    @property
    def last_refresh_ts_ms(self) -> int: ...
```

**Logika:**

1. `GET /v5/market/instruments-info?category=linear&symbol={symbol}`.
1. Parse `priceFilter`, `lotSizeFilter`, `leverageFilter`.
1. Convert all numeric strings → `Decimal`.
1. Validate: all fields non-None, tick_size > 0, qty_step > 0.
1. Store in internal `dict[str, InstrumentMeta]`.
1. Track `_last_refresh_ts_ms`.

**Periodic task:** Co `metadata_refresh_interval_h` godzin (config) → `refresh()`. Jeśli `is_stale()` → trigger `METADATA_STALE` w venue health.

**Demo vs Live:** URL controlled by config (`venues.yaml`):

- Demo: `https://api-demo.bybit.com`
- Live: `https://api.bybit.com`

**Testy:**

- Mock HTTP response z prawdziwym example JSON z Bybit docs.
- Test poprawnego parsowania `Decimal`.
- Test `is_stale` logic.
- Test failure handling (HTTP error, missing fields).

-----

### 5.5 `boot/venue_health.py`

**Cel:** Sprawdzenie dostępności venue przed startem i periodic health monitoring.

**Interfejs:**

```python
class VenueHealthChecker:
    def __init__(self, bybit_url: str, binance_url: str): ...
    async def check_bybit_status(self) -> bool: ...
    async def check_binance_status(self) -> bool: ...
    async def check_bybit_maintenance(self) -> tuple[bool, int | None]:
        """Returns (is_maintenance_soon, minutes_until_maintenance).""" ...
    async def initial_check(self) -> None:
        """Abort if critical venue is down.""" ...
```

**Logika:**

1. Bybit: `GET /v5/market/time` — jeśli response OK, venue alive.
1. Binance: `GET /fapi/v1/time`.
1. Bybit maintenance: `GET /v5/announcements/index?type=new_crypto` + server time comparison.
1. Jeśli maintenance < 15 min → abort boot.

**Periodic task:** Co 60 s (config `venue_status_poll_interval_s`). Detected maintenance → `SYSTEM_ABNORMAL`.

**Testy:**

- Mock HTTP responses.
- Test maintenance detection.

-----

### 5.6 `boot/startup_validator.py`

**Cel:** Orchestration entire boot sequence (sekcja 11.1 blueprintu).

**Interfejs:**

```python
class StartupValidator:
    def __init__(self, config: AppConfig): ...
    async def run_boot_sequence(self) -> BootResult: ...
```

**Logika:**

Implementacja 12-krokowej sekwencji boot z blueprintu. Każdy krok ma explicit pass/fail. Failure na kroku krytycznym = abort z logiem.

**Testy:**

- Integration test: mock all deps, verify sequence order.
- Test failure at each step → correct abort behavior.

-----

### 5.7 `marketdata/ws_reconnect.py`

**Cel:** Generic reconnectable WebSocket wrapper z exponential backoff.

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class ReconnectConfig:
    heartbeat_interval_s: float = 20.0
    max_pong_wait_s: float = 10.0
    reconnect_delay_initial_s: float = 1.0
    reconnect_delay_max_s: float = 30.0
    reconnect_backoff_multiplier: float = 2.0
    max_reconnects_per_5min: int = 5
    reconnect_jitter_max_ms: int = 500

class ReconnectableWebSocket:
    def __init__(
        self,
        url: str,
        on_message: Callable[[bytes], Awaitable[None]],
        on_connect: Callable[[], Awaitable[None]],
        on_disconnect: Callable[[], Awaitable[None]],
        config: ReconnectConfig,
        name: str,  # for logging
    ): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, data: bytes) -> None: ...
    @property
    def is_alive(self) -> bool: ...
    @property
    def reconnect_count_5min(self) -> int: ...
```

**Logika:**

1. Connect → call `on_connect` (subscription logic).
1. Read loop: receive message → call `on_message`.
1. Heartbeat task: send ping co `heartbeat_interval_s`. Jeśli pong nie wraca w `max_pong_wait_s` → reconnect.
1. On disconnect: call `on_disconnect`, wait `delay` (exponential backoff + jitter), reconnect.
1. Track reconnect count w rolling 5-min window. Jeśli > `max_reconnects_per_5min` → raise `TooManyReconnectsError`.

**Testy:**

- Mock WebSocket server.
- Test exponential backoff timing.
- Test max reconnects threshold.
- Test heartbeat timeout detection.

-----

### 5.8 `marketdata/bybit_public_ws.py`

**Cel:** Bybit public WebSocket — orderbook + trades.

**Interfejs:**

```python
class BybitPublicWS:
    def __init__(
        self,
        symbols: list[str],
        on_trade: Callable[[TradeEvent], Awaitable[None]],
        on_book_delta: Callable[[BookDeltaEvent], Awaitable[None]],
        reconnect_config: ReconnectConfig,
    ): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    @property
    def is_alive(self) -> bool: ...
```

**Logika:**

1. URL: `wss://stream.bybit.com/v5/public/linear`
1. On connect: subscribe to:
- `orderbook.50.{symbol}` per symbol
- `orderbook.200.{symbol}` per symbol
- `publicTrade.{symbol}` per symbol
1. On message: parse JSON → route to `on_trade` or `on_book_delta`.
1. TradeEvent construction: map Bybit fields → `TradeEvent` dataclass. `price`/`qty` → `Decimal`. `taker_side` from `S` field. `exchange_ts_ms` from `T` field.
1. BookDeltaEvent construction: `is_snapshot = (type == "snapshot")`. Parse bids/asks → `list[tuple[Decimal, Decimal]]`.
1. On disconnect: `on_book_delta` callback won’t fire → book becomes stale → staleness detection in `local_book.py`.

**Kluczowe detale:**

- Bybit snapshot upon subscription → `is_snapshot = True` → triggers book reset in `local_book.py`.
- Subsequent deltas → `is_snapshot = False`.
- New snapshot at any time → full reset.

**Testy:**

- Mock WebSocket z recorded Bybit messages.
- Test poprawnej konwersji do `TradeEvent` / `BookDeltaEvent`.
- Test subscription message format.

-----

### 5.9 `marketdata/binance_ws.py`

**Cel:** Binance USDⓈ-M public WebSocket — aggTrade + depth.

**Interfejs:**

```python
class BinanceWS:
    def __init__(
        self,
        symbols: list[str],
        on_agg_trade: Callable[[TradeEvent], Awaitable[None]],
        on_depth: Callable[[BookDeltaEvent], Awaitable[None]],
        reconnect_config: ReconnectConfig,
    ): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

**Logika:**

1. URL: `wss://fstream.binance.com/stream?streams={s1}@aggTrade/{s1}@depth/{s2}@aggTrade/...`
1. Symbols lower-cased for Binance: `BTCUSDT` → `btcusdt`.
1. aggTrade parsing: `p` → price, `q` → qty, `m` → taker side (buyer is maker → taker = sell). `T` → exchange_ts_ms.
1. depth parsing: `b` → bids, `a` → asks. `U`, `u`, `pu` → `update_id_from`, `update_id_to`. `is_snapshot = False` (Binance depth stream sends diffs only; snapshot via REST).

**Kluczowe detale:**

- Binance aggTrade: `m = true` → buyer is maker → taker = SELL. `m = false` → taker = BUY.
- Depth diffs require REST snapshot for initialization (handled by `snapshot_fetcher.py`).

**Testy:**

- Mock WebSocket z recorded Binance messages.
- Test `m` flag → correct taker side mapping.
- Test combined stream URL construction.

-----

### 5.10 `marketdata/bybit_private_ws.py`

**Cel:** Bybit private WebSocket — order updates, position updates, execution reports.

**Interfejs:**

```python
class BybitPrivateWS:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        on_order_update: Callable[[OrderEvent], Awaitable[None]],
        on_position_update: Callable[[dict], Awaitable[None]],
        reconnect_config: ReconnectConfig,
        demo: bool = True,
    ): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    @property
    def is_alive(self) -> bool: ...
```

**Logika:**

1. URL: `wss://stream-demo.bybit.com/v5/private` (demo) or `wss://stream.bybit.com/v5/private` (live).
1. Auth: HMAC-SHA256 signature of `"GET/realtime" + expires`. Send auth message on connect.
1. Subscribe: `order`, `position`, `execution`.
1. On order update: parse → `OrderEvent` dataclass.
1. On disconnect: set `is_alive = False` immediately → blocks new order submissions.

**Auth implementation:**

```python
import hmac
import hashlib
import time

def generate_auth_message(api_key: str, api_secret: str) -> dict:
    expires = int(time.time() * 1000) + 10_000
    signature = hmac.new(
        api_secret.encode(),
        f"GET/realtime{expires}".encode(),
        hashlib.sha256
    ).hexdigest()
    return {"op": "auth", "args": [api_key, expires, signature]}
```

**Testy:**

- Test auth message generation.
- Test `OrderEvent` parsing from example Bybit private WS messages.
- Test `is_alive` flag management.

-----

### 5.11 `marketdata/snapshot_fetcher.py`

**Cel:** REST snapshot fetcher dla Binance orderbook i Bybit funding/OI.

**Interfejs:**

```python
class SnapshotFetcher:
    def __init__(self, binance_url: str = "https://fapi.binance.com"): ...

    async def fetch_binance_depth_snapshot(
        self, symbol: str, limit: int = 1000
    ) -> tuple[int, list[tuple[Decimal, Decimal]], list[tuple[Decimal, Decimal]]]:
        """Returns (lastUpdateId, bids, asks).""" ...

    async def fetch_bybit_funding_rate(
        self, symbol: str, bybit_url: str
    ) -> tuple[float, int]:
        """Returns (funding_rate, next_funding_time_ms).""" ...

    async def fetch_bybit_open_interest(
        self, symbol: str, bybit_url: str, interval: str = "5min"
    ) -> list[tuple[int, float]]:
        """Returns list of (ts_ms, oi_value).""" ...
```

**Logika (Binance snapshot):**

1. `GET /fapi/v1/depth?symbol={symbol}&limit=1000`.
1. Parse `lastUpdateId`, `bids`, `asks`.
1. Convert strings → `Decimal`.

**Testy:**

- Mock HTTP z example responses.
- Test Decimal parsing.

-----

### 5.12 `marketdata/normalizer.py`

**Cel:** Normalizacja raw venue messages do kanonicznych event typów.

**Interfejs:**

```python
class EventNormalizer:
    def normalize_bybit_trade(self, raw: dict, recv_ts_ms: int) -> TradeEvent: ...
    def normalize_bybit_book(self, raw: dict, recv_ts_ms: int) -> BookDeltaEvent: ...
    def normalize_binance_agg_trade(self, raw: dict, recv_ts_ms: int) -> TradeEvent: ...
    def normalize_binance_depth(self, raw: dict, recv_ts_ms: int) -> BookDeltaEvent: ...
```

**Logika:**

- Venue-specific field mapping → canonical `MarketEvent` subtypes.
- `recv_ts_ms` = `core.clocks.monotonic_ms()` at receive time.
- `canonical_ts_ms` = `core.clocks.to_canonical_bucket(recv_ts_ms)`.
- Venue field → canonical field mapping (hardcoded per venue).

**Testy:**

- Test each venue’s normalization with example raw messages.
- Verify Decimal precision maintained.
- Verify timestamp assignment.

-----

### 5.13 `marketdata/local_book.py`

**Cel:** Local orderbook reconstruction per venue per symbol.

**Interfejs:**

```python
class LocalBookRebuilder:
    def __init__(self, venue: Venue, symbol: str, tick_size: Decimal): ...
    def apply_snapshot(self, event: BookDeltaEvent) -> None: ...
    def apply_delta(self, event: BookDeltaEvent) -> None: ...
    def get_state(self) -> OrderBookState: ...
    def is_consistent(self) -> bool: ...
    def reset(self) -> None: ...
    def staleness_ms(self, current_ts_ms: int) -> int: ...
```

**Implementacja wewnętrzna:**

- `SortedDict` (from `sortedcontainers`) dla bids (reverse) i asks (forward).
- O(log n) insert/delete/lookup.
- Snapshot: clear all → insert all levels.
- Delta: for each (price, size): if size == 0 → delete, else → upsert.

**Binance-specific logic:**

- `_last_update_id: int` — tracks sequence.
- `_pending_buffer: list[BookDeltaEvent]` — buffered diffs before snapshot.
- `apply_binance_snapshot(lastUpdateId, bids, asks)` — sets initial state.
- `apply_binance_delta(event)` — validates `pu == _last_update_id`. If not → `_needs_resync = True`.

**Bybit-specific logic:**

- Snapshot → full reset.
- Delta → apply.
- New snapshot at any time → full reset.
- No sequence validation needed (Bybit handles via snapshot resend).

**Book validity check (`is_consistent`):**

```python
def is_consistent(self) -> bool:
    state = self.get_state()
    if not state.bids or not state.asks:
        return False
    if state.best_bid >= state.best_ask:
        return False
    if state.spread_ticks < 1:
        return False
    if any(level.size < ZERO_QTY for level in state.bids + state.asks):
        return False
    return True
```

**`OrderBookState` construction:**

- `mid = float(best_bid + best_ask) / 2.0` (float ok — derived value).
- `spread_ticks = int((best_ask - best_bid) / tick_size)`.

**Testy:**

- Test snapshot → correct state.
- Test delta apply → level upsert/delete.
- Test Binance sequence validation → needs_resync on gap.
- Test crossed book detection.
- Property-based: random sequence of snapshots + deltas → book always consistent.

-----

### 5.14 `marketdata/resync_manager.py`

**Cel:** Zarządzanie resync flow dla Binance local book.

**Interfejs:**

```python
class ResyncManager:
    def __init__(
        self,
        book: LocalBookRebuilder,
        fetcher: SnapshotFetcher,
        symbol: str,
        max_retries: int = 3,
    ): ...
    async def initial_sync(self) -> bool: ...
    async def resync_if_needed(self) -> bool: ...
    @property
    def needs_resync(self) -> bool: ...
    @property
    def consecutive_failures(self) -> int: ...
```

**Logika (Binance runbook z sekcji 13.1 blueprintu):**

1. Start depth stream buffering.
1. Fetch REST snapshot → `lastUpdateId`.
1. Drop buffered events where `u < lastUpdateId`.
1. First applied event must satisfy `U <= lastUpdateId <= u`.
1. Apply subsequent events checking `pu == previous_u`.
1. Failure → increment `consecutive_failures` → retry.
1. 3 failures → venue = DEGRADED.

**Testy:**

- Test full resync sequence with mock snapshot + buffered events.
- Test sequence validation logic.
- Test failure counting.

-----

### 5.15 `marketdata/canonical_clock.py`

**Cel:** 100 ms canonical tick generator.

**Interfejs:**

```python
class CanonicalClock:
    def __init__(
        self,
        tick_ms: int = 100,
        on_tick: Callable[[int], Awaitable[None]] | None = None,
    ): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    @property
    def current_bucket(self) -> int: ...
    @property
    def tick_count(self) -> int: ...
```

**Logika:**

- `asyncio.Task` loop: sleep until next 100 ms boundary.
- On tick: call `on_tick(canonical_ts_ms)`.
- Drift compensation: measure actual sleep duration, adjust next sleep to stay aligned.

**Testy:**

- Test tick generation timing (within ±5 ms tolerance).
- Test tick count accuracy.

-----

### 5.16 `storage/raw_writer.py`

**Cel:** Append-only writer dla raw market events do Parquet.

**Interfejs:**

```python
class RawEventWriter:
    def __init__(self, base_dir: str, flush_interval_s: float = 5.0, max_buffer_size: int = 10000): ...
    def write_trade(self, event: TradeEvent) -> None: ...
    def write_book_delta(self, event: BookDeltaEvent) -> None: ...
    async def flush(self) -> None: ...
    async def close(self) -> None: ...
```

**Logika:**

- Bufferuje eventy w liście.
- Co `flush_interval_s` lub gdy buffer > `max_buffer_size` → zapisz do Parquet.
- Plik naming: `{base_dir}/raw_trades/{venue}/{symbol}/{date}/trades_{ts}.parquet`.
- Schema: explicit PyArrow schema matching `TradeEvent` fields.

**Testy:**

- Test write → flush → read back correct data.
- Test auto-flush on buffer full.

-----

### 5.17 `storage/parquet_store.py`

**Cel:** Generic Parquet read/write utilities.

**Interfejs:**

```python
class ParquetStore:
    @staticmethod
    def write(path: str, data: list[dict], schema: pa.Schema) -> None: ...
    @staticmethod
    def read(path: str) -> pa.Table: ...
    @staticmethod
    def append(path: str, data: list[dict], schema: pa.Schema) -> None: ...
```

-----

### 5.18 `monitoring/health.py`

**Cel:** Health monitor — agreguje status wszystkich komponentów.

**Interfejs:**

```python
@dataclass(slots=True)
class HealthStatus:
    bybit_public_ws_alive: bool
    binance_ws_alive: bool
    bybit_private_ws_alive: bool
    bybit_book_valid: dict[str, bool]    # per symbol
    binance_book_valid: dict[str, bool]  # per symbol
    metadata_fresh: bool
    ntp_ok: bool
    venue_health_state: VenueHealthState
    last_check_ts_ms: int

class HealthMonitor:
    def __init__(self, check_interval_s: float = 10.0): ...
    def register_component(self, name: str, health_fn: Callable[[], bool]) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def get_status(self) -> HealthStatus: ...
    def compute_venue_health_state(self) -> VenueHealthState: ...
```

**Logika:**

Periodically polls all registered health functions. Derives `VenueHealthState` z kombinacji stanów komponentów (sekcja 25 blueprintu).

-----

### 5.19 `monitoring/latency.py`

**Cel:** Tracking latencji `recv_ts_ms - exchange_ts_ms` per venue.

**Interfejs:**

```python
class LatencyTracker:
    def __init__(self, window_size: int = 1000): ...
    def record(self, venue: Venue, exchange_ts_ms: int, recv_ts_ms: int) -> None: ...
    def get_median_ms(self, venue: Venue) -> float: ...
    def get_p99_ms(self, venue: Venue) -> float: ...
    def get_latency_score(self, venue: Venue) -> float:
        """1 - min(median_latency_ms / 500, 1.0)""" ...
    def check_clock_drift(self, venue: Venue) -> tuple[bool, float]:
        """Returns (is_ok, median_drift_ms). ok if median < 2000ms.""" ...
```

-----

### 5.20 `monitoring/venue_status.py`

**Cel:** Periodic polling Bybit system status.

**Interfejs:**

```python
class VenueStatusMonitor:
    def __init__(self, bybit_url: str, poll_interval_s: float = 60.0): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    @property
    def is_maintenance_imminent(self) -> bool: ...
    @property
    def minutes_until_maintenance(self) -> int | None: ...
```

-----

### 5.21 `shutdown/graceful_shutdown.py`

**Cel:** Graceful shutdown sequence (sekcja 30 blueprintu).

**Interfejs:**

```python
class GracefulShutdown:
    def __init__(self, components: ShutdownComponents): ...
    async def execute(self, reason: str, is_kill_switch: bool = False) -> None: ...

@dataclass
class ShutdownComponents:
    signal_engine: Any          # has stop() method
    order_router: Any           # has cancel_all(), market_close_all()
    ws_connections: list[Any]   # have stop() methods
    log_writers: list[Any]      # have flush(), close() methods
    state_snapshot_fn: Callable  # writes final state
```

**Logika:**

Implementacja 8-krokowej sekwencji z sekcji 30.2 blueprintu:

1. Stop signal engine.
1. Cancel all pending orders via REST.
1. Wait ≤ 5 s for WS cancel confirmations.
1. Handle open positions (KILL_SWITCH → market close; graceful → keep SL).
1. Close all WS connections.
1. Flush all log buffers.
1. Write final state snapshot.
1. Exit.

**Signal handlers:**

```python
import signal

def register_signal_handlers(shutdown: GracefulShutdown):
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(
            shutdown.execute(reason=f"Signal {sig.name}", is_kill_switch=False)
        ))
```

**Testy:**

- Test sequence order via mock components with call recording.
- Test KILL_SWITCH vs graceful different behavior.

-----

### 5.22 `app.py` (skeleton)

**Cel:** Main entry point. Orchestruje boot → run → shutdown.

```python
async def main():
    # 1. Load config
    config = load_config("config/base.yaml")

    # 2. Boot sequence
    validator = StartupValidator(config)
    boot_result = await validator.run_boot_sequence()

    # 3. Register shutdown handlers
    shutdown = GracefulShutdown(...)
    register_signal_handlers(shutdown)

    # 4. Main loop (runs until shutdown)
    await run_main_loop(...)

if __name__ == "__main__":
    import uvloop
    uvloop.install()
    asyncio.run(main())
```

-----

### 5.23 Acceptance gate — Faza 1

System musi:

1. Bootować z walidacją environment, NTP, metadata.
1. Łączyć się z Bybit public WS (3 symbole × 3 subskrypcje).
1. Łączyć się z Binance WS (3 symbole × 2 streams).
1. Łączyć się z Bybit private demo WS (auth + subscribe).
1. Budować poprawne local books dla obu venue (6 total).
1. Logować raw events do Parquet (trades + book deltas).
1. Obsługiwać WS reconnect z exponential backoff.
1. Obsługiwać Binance book resync (REST snapshot + buffered diffs).
1. Generować canonical clock ticks co 100 ms.
1. Zamykać się gracefully na SIGTERM/SIGINT.
1. Wykrywać staleness (book age > 5 s), NTP drift, venue down.

**Test integration — Faza 1:**

```python
async def test_phase1_integration():
    """Boot → connect → receive 60s of data → verify books valid → shutdown."""
    config = load_test_config()
    app = App(config)
    await app.boot()

    await asyncio.sleep(60)

    for symbol in config.system.symbols:
        assert app.bybit_books[symbol].is_consistent()
        assert app.binance_books[symbol].is_consistent()

    assert app.raw_writer.event_count > 0
    assert app.health_monitor.get_status().venue_health_state == VenueHealthState.FULLY_OPERATIONAL

    await app.shutdown("test complete")
```

-----

## 6. Faza 2 — Context

### 6.1 Cel

Działający context layer: session model, value framework (VWAP, profile, levels), regime engine, noise floor. System wie „gdzie jest cena w kontekście struktury rynku” i „jaki jest obecny regime”.

### 6.1.1 Kolejność implementacji

```
context/session_model.py
context/vwap_engine.py
context/value_profile.py
context/level_map.py
context/volatility_filters.py
context/regime_engine.py
context/funding_oi_context.py
```

-----

### 6.2 `context/session_model.py`

**Cel:** Zarządzanie session windows — czy system jest w active session.

**Interfejs:**

```python
class SessionModel:
    def __init__(self, config: SessionsConfig): ...
    def get_active_session(self, utc_now_ms: int) -> SessionName: ...
    def is_trading_allowed(self, utc_now_ms: int) -> bool: ...
    def session_elapsed_minutes(self, utc_now_ms: int) -> float: ...
    def get_session_boundaries(self, session: SessionName) -> tuple[int, int]:
        """Returns (start_utc_ms, end_utc_ms) for today's instance of session.""" ...
```

**Logika:**

- Parse session config windows → daily UTC time ranges.
- `EU_OPEN`: 08:00–12:00 UTC.
- `US_OVERLAP`: 14:00–20:00 UTC.
- `FUNDING_ADJACENT`: dynamiczny — bazowany na `nextFundingTime` (z funding_oi_context).
- Poza oknami → `INACTIVE`.
- `is_trading_allowed = active_session != INACTIVE`.

**Testy:**

- Test boundary conditions (exact start/end of session).
- Test INACTIVE outside windows.
- Test FUNDING_ADJACENT dynamic window.

-----

### 6.3 `context/vwap_engine.py`

**Cel:** Rolling VWAP computation.

**Interfejs:**

```python
class VwapEngine:
    def __init__(self, symbol: str): ...
    def update(self, price: float, qty: float, ts_ms: int) -> None: ...
    def get_session_vwap(self) -> float: ...
    def get_rolling_24h_vwap(self) -> float: ...
    def get_micro_vwap_60min(self) -> float: ...
    def reset_session(self) -> None: ...
```

**Logika:**

- Accumulate `sum(price * qty)` i `sum(qty)` w rolling windows.
- Session VWAP: reset na nowej sesji.
- Rolling 24h: circular buffer z prunowaniem starych danych.
- Micro 60 min: rolling 60 min window.

**Implementacja:**

- Dwa circular buffers: `(ts_ms, price * qty, qty)`.
- Prune entries older than window.
- VWAP = `sum_pq / sum_q`.

**Testy:**

- Known data → known VWAP.
- Session reset clears accumulator.
- Rolling window prunes correctly.

-----

### 6.4 `context/value_profile.py`

**Cel:** Volume profile (TPO-style), POC, Value Area.

**Interfejs:**

```python
@dataclass(slots=True)
class VolumeProfileResult:
    poc: float
    value_area_high: float
    value_area_low: float
    hvn_levels: list[float]
    lvn_levels: list[float]
    total_volume: float

class VolumeProfileEngine:
    def __init__(self, symbol: str, tick_size: float, va_pct: float = 0.70): ...
    def update(self, price: float, qty: float) -> None: ...
    def compute(self) -> VolumeProfileResult: ...
    def reset(self) -> None: ...
```

**Logika:**

1. Binuj trade volume do price buckets (1 tick resolution).
1. POC = bucket z max volume.
1. Value Area: ekspanduj od POC bucket w obie strony aż 70% total volume jest pokryte.
1. HVN: local maxima w volume distribution (top 5 poza POC).
1. LVN: local minima z volume < 20th percentile.

**Implementacja:**

- `defaultdict[int, float]` — price_bucket → volume.
- Bucket key = `int(price / tick_size)`.
- POC = `max(buckets, key=buckets.get)`.
- VA expansion: iteruj od POC, w każdym kroku dodaj bucket z wyższym volume (bid-side lub ask-side), aż `cum_vol / total_vol >= 0.70`.

**Testy:**

- Uniform distribution → POC ≈ center, VA ≈ full range.
- Bimodal distribution → POC at taller peak, VA covers taller peak.
- Single price → POC = that price, VA = single bucket.

-----

### 6.5 `context/level_map.py`

**Cel:** Agregacja wszystkich mapped levels dla sweep detection.

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class MappedLevel:
    price: float
    level_type: SweepLevelType
    strength: float     # 0–1, jak „ważny" jest level
    created_ts_ms: int

class LevelMap:
    def __init__(self, symbol: str, max_levels: int = 50): ...
    def update_from_context(self, ctx: SessionContext) -> None: ...
    def add_failed_auction(self, price: float, ts_ms: int) -> None: ...
    def get_nearby_levels(self, current_price: float, max_distance_bps: float) -> list[MappedLevel]: ...
    def get_closest_level(self, price: float, side: TakerSide) -> MappedLevel | None: ...
    def clear_stale(self, max_age_ms: int) -> None: ...
```

**Logika:**

- Zbiera levele z `SessionContext`: prior high/low, VAH/VAL, POC, LVN edges.
- Dodaje failed auction extremes (z sweep_detector, gdy sweep potwierdzony → level staje się „failed auction” po odrzuceniu).
- `get_nearby_levels`: zwraca levele w odległości `<= max_distance_bps` od `current_price`.
- `get_closest_level(price, side=SELL)`: dla longa — najbliższy level PONIŻEJ price. Dla shorta — POWYŻEJ.

**Testy:**

- Test level construction from SessionContext.
- Test proximity filtering.
- Test stale level cleanup.

-----

### 6.6 `context/volatility_filters.py`

**Cel:** Realized volatility computation i noise floor.

**Interfejs:**

```python
class VolatilityEngine:
    def __init__(self, symbol: str): ...
    def update(self, price: float, ts_ms: int) -> None: ...

    @property
    def realized_vol_short(self) -> float:
        """5 min rolling realized vol, annualized.""" ...

    @property
    def realized_vol_baseline(self) -> float:
        """2 h rolling realized vol, annualized.""" ...

    @property
    def vol_ratio(self) -> float:
        """short / baseline.""" ...

    @property
    def local_noise_floor(self) -> float:
        """Median abs tick-to-tick change, last 500 trades, in ticks.""" ...

    @property
    def short_atr_1min(self) -> float:
        """1 min ATR.""" ...
```

**Logika:**

- `realized_vol`: `std(log_returns) * sqrt(annualization_factor)`.
- `local_noise_floor`: `np.median(np.abs(np.diff(recent_prices_in_ticks)))` over last 500 trades.
- `short_atr_1min`: True Range over rolling 1 min OHLC bars (derived from trade stream).

**Testy:**

- Known price series → known vol.
- Noise floor computation correctness.

-----

### 6.7 `context/regime_engine.py`

**Cel:** Klasyfikacja aktualnego regime’u rynkowego.

**Interfejs:**

```python
class RegimeEngine:
    def __init__(self, config: RegimeConfig): ...
    def update(
        self,
        session_ctx: SessionContext,
        vol_engine: VolatilityEngine,
        current_price: float,
        session_elapsed_min: float,
    ) -> RegimeState: ...
```

**Logika (sekcja 14.5 blueprintu):**

1. Jeśli `session_elapsed_min < min_session_data_minutes` → `INVALID`.
1. Compute 4 classification features:
- `vol_ratio = vol_engine.vol_ratio`
- `price_vs_va`: WITHIN_VA / TOUCHES_BOUNDARY / OUTSIDE_NEAR / OUTSIDE_EXTENDING
- `range_expansion`: current session range vs rolling average session range
- `poc_migration_rate`: abs(POC change) / elapsed hours
1. Score each regime candidate based on sekcja 14.5 table.
1. Select regime with highest score.
1. `regime_confidence` = weighted agreement across 4 features. Jeśli top candidate score < 0.65 → `INVALID`.

**Fair value anchor computation (sekcja 14.8):**

```python
if session_elapsed_min >= 30:
    fair_value_anchor = (
        0.50 * session_ctx.session_vwap
        + 0.30 * session_ctx.session_poc
        + 0.20 * micro_profile_60min_poc
    )
else:
    fair_value_anchor = rolling_24h_vwap
```

**Testy:**

- Test each regime classification scenario.
- Test INVALID when insufficient data.
- Test fair value anchor computation.
- Test confidence calculation.

-----

### 6.8 `context/funding_oi_context.py`

**Cel:** Periodic REST polling funding rate i OI, z-score computation.

**Interfejs:**

```python
class FundingOIContext:
    def __init__(
        self,
        symbols: list[str],
        fetcher: SnapshotFetcher,
        bybit_url: str,
        poll_interval_s: float = 60.0,
    ): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def get_funding_zscore(self, symbol: str) -> float | None: ...
    def get_oi_delta_5m_zscore(self, symbol: str) -> float | None: ...
    def get_funding_rate(self, symbol: str) -> float | None: ...
    def get_next_funding_time(self, symbol: str) -> int | None: ...
```

**Logika:**

1. Poll `GET /v5/market/tickers` co 60 s → extract `fundingRate`, `nextFundingTime`.
1. Poll `GET /v5/market/open-interest?interval=5min` co 60 s → extract latest OI.
1. Funding z-score: rolling window 168 measurements (~7 days at 8h funding). `zscore = (current - mean) / std`.
1. OI delta 5m z-score: `oi_delta = current_oi - previous_oi`. Rolling window 60 measurements (~5h). `zscore = (delta - mean_delta) / std_delta`.

**Testy:**

- Test z-score computation with known data.
- Test handling of missing data (first N polls).
- Mock HTTP responses.

-----

### 6.9 Session drift monitor

**Cel:** Adaptive session monitoring (sekcja 14.2 blueprintu).

Zaimplementowane wewnątrz `context/session_model.py` jako dodatkowa metoda:

```python
class SessionModel:
    ...
    def check_session_drift(self, hourly_volume: dict[int, float]) -> bool:
        """Returns True if > session_drift_alert_pct volume falls outside defined windows.""" ...
```

Monitoring task w `app.py`: co 1h aggregate volume per hour, call `check_session_drift`. Jeśli True → log WARNING `SESSION_DRIFT`.

-----

### 6.10 `SessionContext` assembly

W `app.py` (lub dedicated orchestrator), na każdym canonical tick:

```python
session_ctx = SessionContext(
    active_session=session_model.get_active_session(now_ms),
    session_vwap=vwap_engine.get_session_vwap(),
    session_poc=profile.compute().poc,
    value_area_high=profile.compute().value_area_high,
    value_area_low=profile.compute().value_area_low,
    hvn_levels=profile.compute().hvn_levels,
    lvn_levels=profile.compute().lvn_levels,
    prior_high=prior_day.high,
    prior_low=prior_day.low,
    prior_poc=prior_day.poc,
    prior_vah=prior_day.vah,
    prior_val=prior_day.val,
)
```

-----

### 6.11 Acceptance gate — Faza 2

System musi:

1. Poprawnie identyfikować active session (EU_OPEN, US_OVERLAP, INACTIVE).
1. Liczyć session VWAP z < 0.01% error vs known data.
1. Generować volume profile z POC, VAH, VAL.
1. Emitować mapped levels (prior H/L, VA, POC, LVN).
1. Klasyfikować regime poprawnie dla known market scenarios.
1. Liczyć noise floor z median abs tick change.
1. Liczyć fair value anchor (weighted composite).
1. Pollować funding/OI i liczyć z-scores.
1. Nie generować sygnałów (Faza 4) — tylko context.

**Test integration — Faza 2:**

Replay 1 day of recorded raw events → verify context output matches manually computed values (VWAP, POC, VAH, VAL, regime classification).

-----

## 7. Faza 3 — Features

### 7.1 Cel

Kompletny feature engine: wszystkie 50+ features z sekcji 15 blueprintu liczone na każdym canonical tick (100 ms) i assemblowane do `MicrostructureFeatures` snapshot.

### 7.1.1 Kolejność implementacji

```
features/obi.py
features/ofi.py
features/microprice.py
features/cvd.py
features/lad.py
features/trade_efficiency.py
features/sweep_detector.py
features/absorption.py
features/exhaustion.py
features/replenishment.py
features/spoof_probability.py
features/iceberg_inference.py
features/liquidation_burst.py
features/feature_snapshot.py
storage/feature_store.py
```

-----

### 7.2 `features/obi.py`

**Cel:** Order Book Imbalance computation.

**Interfejs:**

```python
class OBICalculator:
    def compute(self, book: OrderBookState, bandwidth_bps: float) -> float:
        """
        OBI = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        where volume is summed within `bandwidth_bps` from mid.
        Returns float in [-1, 1].
        """ ...

    def compute_queue_imbalance(self, book: OrderBookState, top_n: int) -> float:
        """
        QI = (sum_bid_size_topN - sum_ask_size_topN) / (sum_bid_size_topN + sum_ask_size_topN)
        """ ...
```

**Logika:**

1. Compute mid.
1. `bandwidth_price = mid * bandwidth_bps / 10000`.
1. Sum bid volume where `price >= mid - bandwidth_price`.
1. Sum ask volume where `price <= mid + bandwidth_price`.
1. OBI = `(bid_vol - ask_vol) / (bid_vol + ask_vol + epsilon)`.

**epsilon:** `1e-12` aby uniknąć division by zero na pustym booku.

**Per venue, per bandwidth:** Osobny call dla Bybit 5bp, Bybit 10bp, Binance 5bp, Binance 10bp.

**Testy:**

- Symmetric book → OBI ≈ 0.
- All bids, no asks → OBI ≈ 1.
- Empty book → OBI = 0 (epsilon guard).

-----

### 7.3 `features/ofi.py`

**Cel:** Order Flow Imbalance — change in order book depth over time.

**Interfejs:**

```python
class OFICalculator:
    def __init__(self, top_n: int = 10): ...
    def update(self, book_state: OrderBookState, ts_ms: int) -> None: ...
    def get_ofi_1s(self) -> float: ...
```

**Logika:**

OFI = suma zmian w depth po bid-side minus suma zmian w depth po ask-side, over time window.

Na każdym book update:

1. Snapshot top-N bids i asks (price, size).
1. Compare z previous snapshot:
- Jeśli bid price unchanged: `delta_bid = new_size - old_size`.
- Jeśli bid price improved (higher): `delta_bid = new_size`.
- Jeśli bid price worsened (lower): `delta_bid = -old_size`.
1. Analogicznie dla asks (ale z odwróconym znakiem).
1. OFI = `sum(delta_bids) - sum(delta_asks)` over 1 s window.

**Testy:**

- Stable book → OFI ≈ 0.
- Bid size increasing → OFI > 0.
- Ask size increasing → OFI < 0.

-----

### 7.4 `features/microprice.py`

**Cel:** Microprice — volume-weighted mid price.

**Interfejs:**

```python
class MicropriceCalculator:
    def compute(self, book: OrderBookState) -> float:
        """
        microprice = (best_bid * ask_size_L1 + best_ask * bid_size_L1) / (bid_size_L1 + ask_size_L1)
        """ ...

    def compute_offset_bps(self, book: OrderBookState) -> float:
        """
        (microprice - mid) / mid * 10000
        Positive = microprice above mid (buying pressure).
        """ ...
```

**Testy:**

- Equal L1 sizes → microprice = mid.
- Bid size >> ask size → microprice closer to ask (price going up).

-----

### 7.5 `features/cvd.py`

**Cel:** Cumulative Volume Delta w rolling windows.

**Interfejs:**

```python
class CVDCalculator:
    def __init__(self, venue: Venue): ...
    def update(self, trade: TradeEvent) -> None: ...
    def get_cvd(self, window_s: float) -> float:
        """Signed cumulative volume over window. Buy = +, Sell = -.""" ...
```

**Logika:**

- Ring buffer z `(ts_ms, signed_notional)`.
- `signed_notional = notional if BUY else -notional`.
- `get_cvd(window_s)`: sum signed_notional where `ts_ms > now - window_s * 1000`.

**Outputs:** `cvd_1s`, `cvd_3s`, `cvd_10s`.

**Testy:**

- All buys → CVD > 0.
- Equal buy/sell → CVD ≈ 0.
- Window pruning correctness.

-----

### 7.6 `features/lad.py`

**Cel:** Large Aggressor Delta.

**Interfejs:**

```python
class LADCalculator:
    def __init__(self, venue: Venue, threshold_window: int = 20000): ...
    def update(self, trade: TradeEvent) -> None: ...
    def get_threshold(self) -> float:
        """Rolling 97th percentile notional.""" ...
    def get_lad_buy_1s(self) -> float: ...
    def get_lad_sell_1s(self) -> float: ...
    def get_lad_imbalance_1s(self) -> float: ...
    def get_lad_buy_count_3s(self) -> int: ...
    def get_lad_sell_count_3s(self) -> int: ...
```

**Logika:**

1. Maintain ring buffer of last 20000 trade notionals → compute rolling 97th percentile.
1. Separately maintain buffer of large trades (notional >= threshold) with timestamps.
1. Aggregate per side, per time window.
1. `lad_imbalance = (buy - sell) / (buy + sell + epsilon)`.

**Testy:**

- Test threshold computation with known distribution.
- Test imbalance with skewed large trades.

-----

### 7.7 `features/trade_efficiency.py`

**Cel:** Trade Efficiency Score — price impact per unit notional.

**Interfejs:**

```python
class TradeEfficiencyCalculator:
    def __init__(self): ...
    def update(self, price: float, notional: float, ts_ms: int) -> None: ...
    def get_efficiency_1s(self) -> float:
        """abs(price_change_1s) / total_notional_1s. Low = absorption.""" ...
    def get_signed_notional(self, window_s: float) -> float: ...
```

-----

### 7.8 `features/sweep_detector.py`

**Cel:** Formalna detekcja sweep events (sekcja 16 blueprintu).

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class SweepEvent:
    symbol: str
    side: TakerSide           # which side got swept (SELL = sweep down)
    level: MappedLevel
    penetration_ticks: int
    penetration_zscore: float
    peak_price: float
    return_price: float
    return_ratio: float
    failure_time_ms: int
    notional_in_sweep: float
    detected_at_ms: int

class SweepDetector:
    def __init__(
        self,
        symbol: str,
        level_map: LevelMap,
        noise_floor_fn: Callable[[], float],
        tick_size: float,
        max_failure_ms: int = 3000,
    ): ...

    def update_trade(self, trade: TradeEvent) -> None: ...
    def update_book(self, book: OrderBookState) -> None: ...
    def check(self, ts_ms: int) -> SweepEvent | None: ...

    # Feature outputs
    @property
    def sweep_detected(self) -> bool: ...
    @property
    def sweep_side(self) -> str: ...
    @property
    def sweep_distance_ticks(self) -> int: ...
    @property
    def sweep_distance_zscore(self) -> float: ...
    @property
    def sweep_return_ratio(self) -> float: ...
    @property
    def sweep_failure_time_ms(self) -> int: ...
    @property
    def sweep_level_type(self) -> str: ...
    @property
    def followthrough_failure_score(self) -> float: ...
    @property
    def reentry_into_range(self) -> bool: ...
```

**Logika (sekcja 16.1 blueprintu):**

State machine interna:

```
IDLE → MONITORING → PENETRATING → WATCHING_RETURN → SWEEP_CONFIRMED / BREAKOUT
```

1. **MONITORING:** Price approaches mapped level (within 5 ticks). Track.
1. **PENETRATING:** Price crosses level by >= `max(2 ticks, noise_floor)`.
- Check volume condition: notional in sweep zone >= 75th percentile 1s notional.
- Start timer.
1. **WATCHING_RETURN:** Wait for price to return to/past level.
- If returns within `max_failure_ms` AND `followthrough_failure_score >= 0.5` → **SWEEP_CONFIRMED**.
- If price continues and makes new HH/LL for > 3 s → **BREAKOUT** (not a sweep).
- If timer expires without return → **BREAKOUT**.
1. **SWEEP_CONFIRMED:** Emit `SweepEvent`. Compute all sweep features.

**`followthrough_failure_score` computation:**

- After penetration, measure max additional price progress beyond initial penetration.
- `followthrough = max_additional_progress / initial_penetration_distance`.
- `score = 1 - min(followthrough, 1.0)`.
- Score 1.0 = zero continuation (perfect failure). Score 0.0 = doubled the extension (breakout).

**`sweep_distance_zscore`:**

- Maintain rolling buffer of last 500 wick distances (any level test, not just sweeps).
- `zscore = (current_distance - mean) / std`.

**Testy:**

- Test clean sweep scenario → SWEEP_CONFIRMED.
- Test breakout scenario → not a sweep.
- Test too shallow → ignore.
- Test volume condition not met → not a sweep.
- Test timeout → not a sweep.

-----

### 7.9 `features/absorption.py`

**Cel:** Absorption score — volume absorbed without price progress.

**Interfejs:**

```python
class AbsorptionCalculator:
    def __init__(self, venue: Venue): ...
    def update(self, trade: TradeEvent, book: OrderBookState) -> None: ...
    def get_score(self, direction: TakerSide, window_s: float = 3.0) -> float:
        """0–1. High = lots of volume absorbed with no movement.""" ...
```

**Logika:**

1. Track volume in sweep direction over window.
1. Track price progress in sweep direction over window.
1. `absorption = volume_swept / (volume_swept + epsilon)` scaled by `1 - price_progress_ratio`.
1. Normalize to 0–1.

-----

### 7.10 `features/exhaustion.py`

**Cel:** Exhaustion score — declining trade rate and notional after sweep.

**Interfejs:**

```python
class ExhaustionCalculator:
    def __init__(self): ...
    def update(self, trade: TradeEvent) -> None: ...
    def get_score(self, direction: TakerSide, window_s: float = 3.0) -> float:
        """0–1. High = trade rate and notional declining in sweep direction.""" ...
```

**Logika:**

1. Compare trade rate + notional in direction-side: first 1s vs last 1s of window.
1. If declining → score increases toward 1.0.
1. `score = max(0, 1 - (recent_rate / initial_rate))`.

-----

### 7.11 `features/replenishment.py`

**Cel:** Replenishment score — how fast support-side depth restores after sweep.

**Interfejs:**

```python
class ReplenishmentCalculator:
    def __init__(self): ...
    def update(self, book: OrderBookState, ts_ms: int) -> None: ...
    def get_score(self, support_side: TakerSide) -> float:
        """0–1. High = support depth quickly restored post-sweep.""" ...
```

**Logika:**

1. Record depth on support side (bid for long setup, ask for short) right after sweep.
1. Track how quickly depth recovers to pre-sweep level.
1. `score = min(current_depth / pre_sweep_depth, 1.0)`.

-----

### 7.12 `features/spoof_probability.py`

**Cel:** Spoof detection — rapid pull of visible depth.

**Interfejs:**

```python
class SpoofCalculator:
    def __init__(self): ...
    def update(self, book: OrderBookState, ts_ms: int) -> None: ...
    def get_probability(self) -> float:
        """0–1. High = likely spoofing activity on visible depth.""" ...
```

**Logika:**

1. Track large depth additions on one side.
1. If depth disappears rapidly (within 200 ms) without being filled → spoof indicator.
1. `probability = rapid_pull_events / total_large_additions` over rolling window.

-----

### 7.13 `features/iceberg_inference.py`

**Cel:** Inferencja ukrytej płynności.

**Interfejs:**

```python
class IcebergInference:
    def __init__(self): ...
    def update(self, trade: TradeEvent, book: OrderBookState) -> None: ...
    def get_score(self) -> float:
        """0–1. High = likely hidden liquidity on level.""" ...
```

**Logika:**

1. Level repeatedly tested: visible depth consumed, but price doesn’t move.
1. Track: volume traded at level vs visible depth at level. Ratio >> 1 → iceberg.
1. `score = min((volume_at_level / visible_depth_at_level) / 3.0, 1.0)`.

-----

### 7.14 `features/liquidation_burst.py`

**Cel:** Detekcja cascading liquidation events.

**Interfejs:**

```python
class LiquidationBurstDetector:
    def __init__(self): ...
    def update(self, trade: TradeEvent) -> None: ...
    def get_score(self) -> float:
        """0–1. High = sweep likely driven by cascading liquidations.""" ...
```

**Logika:**

1. Detect burst pattern: rapid sequence of same-direction trades with increasing notional.
1. Combined with: widening spread, one-directional book depletion.
1. `score` based on pattern intensity relative to normal trade distribution.

-----

### 7.15 `features/feature_snapshot.py`

**Cel:** Assemblacja kompletnego `MicrostructureFeatures` na każdym canonical tick.

**Interfejs:**

```python
class FeatureSnapshotAssembler:
    def __init__(
        self,
        obi_calc: dict[Venue, OBICalculator],
        ofi_calc: dict[Venue, OFICalculator],
        microprice_calc: dict[Venue, MicropriceCalculator],
        cvd_calc: dict[Venue, CVDCalculator],
        lad_calc: dict[Venue, LADCalculator],
        trade_eff_calc: TradeEfficiencyCalculator,
        sweep_detector: dict[str, SweepDetector],     # per symbol
        absorption_calc: AbsorptionCalculator,
        exhaustion_calc: ExhaustionCalculator,
        replenishment_calc: ReplenishmentCalculator,
        spoof_calc: SpoofCalculator,
        iceberg_calc: IcebergInference,
        liq_burst_calc: LiquidationBurstDetector,
        latency_tracker: LatencyTracker,
        funding_oi: FundingOIContext,
        context: Callable[[], tuple[SessionContext, RegimeState]],
        books: dict[tuple[Venue, str], LocalBookRebuilder],
    ): ...

    def assemble(self, symbol: str, ts_ms: int) -> MicrostructureFeatures: ...
```

**Logika:**

Single method that queries every calculator and assembles the full `MicrostructureFeatures` dataclass. Called once per canonical tick per symbol.

**Market quality features computation:**

```python
spread_pctl = rolling_percentile(spread_history, current_spread)
spread_stability = 1 - min(cv_spread_60s, 1.0)
depth_stability = 1 - min(cv_depth_60s, 1.0)
data_quality = mean(book_valid_bybit, book_valid_binance, freshness_ok, seq_ok)
latency_score = latency_tracker.get_latency_score(Venue.BYBIT)
```

**Testy:**

- Test assembly with mock calculators → all fields populated.
- Test with degraded venue (Binance down) → Binance features = NaN/0, rest populated.

-----

### 7.16 `storage/feature_store.py`

**Cel:** Parquet storage for feature snapshots.

**Interfejs:**

```python
class FeatureStore:
    def __init__(self, base_dir: str): ...
    def write(self, snapshot: MicrostructureFeatures) -> None: ...
    async def flush(self) -> None: ...
```

Schema: explicit PyArrow schema matching all `MicrostructureFeatures` fields.

-----

### 7.17 Acceptance gate — Faza 3

System musi:

1. Na każdym 100 ms tick generować kompletny `MicrostructureFeatures` dla każdego symbolu.
1. Poprawnie liczyć OBI (± known values na known book state).
1. Poprawnie liczyć OFI (sign flip detection).
1. Poprawnie liczyć microprice offset.
1. Poprawnie liczyć CVD w multiple windows.
1. Poprawnie identyfikować large trades (97th percentile threshold).
1. Poprawnie detekować sweep events (true positive na known sweep, true negative na breakout).
1. Generować absorption/exhaustion/replenishment scores.
1. Zapisywać feature snapshots do Parquet.

**Test integration — Faza 3:**

Replay 1 day of raw events → generate feature snapshots → verify:

- OBI ranges [-1, 1].
- CVD correctly signed.
- Sweep events match manual annotation.
- Feature snapshot completeness (no None/NaN for required fields).

-----

## 8. Faza 4 — Signals

### 8.1 Cel

Hard gates, scoring, setup detection. System generuje `SignalDecision` na każdym canonical tick (ale w ogromnej większości = `direction: none`).

### 8.1.1 Kolejność implementacji

```
signals/hard_gates.py
signals/score_normalizer.py
signals/scorer.py
signals/long_setup.py
signals/short_setup.py
signals/signal_router.py
storage/order_log.py (signal decisions logging)
```

-----

### 8.2 `signals/hard_gates.py`

**Cel:** Sprawdzenie 8 hard gates (sekcja 18 blueprintu).

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class GateResult:
    gate_name: str
    passed: bool
    reason: str   # human-readable explanation if failed

class HardGates:
    def __init__(self, config: HardGatesConfig): ...
    def evaluate(
        self,
        features: MicrostructureFeatures,
        regime: RegimeState,
        risk_snapshot: RiskSnapshot,
        intended_risk_r: float,
        book_valid_bybit: bool,
        book_valid_binance: bool,
        private_ws_alive: bool,
    ) -> tuple[bool, dict[str, GateResult]]:
        """Returns (all_passed, per_gate_results).""" ...
```

**Logika:**

8 gate functions, każdy zwraca `GateResult`:

```python
def _g1_regime_ok(self, regime: RegimeState) -> GateResult: ...
def _g2_level_ok(self, features: MicrostructureFeatures) -> GateResult: ...
def _g3_sweep_ok(self, features: MicrostructureFeatures) -> GateResult: ...
def _g4_return_ok(self, features: MicrostructureFeatures) -> GateResult: ...
def _g5_flow_confirm_ok(self, features: MicrostructureFeatures) -> GateResult: ...
def _g6_execution_ok(self, features: MicrostructureFeatures, ...) -> GateResult: ...
def _g7_target_ok(self, features: MicrostructureFeatures) -> GateResult: ...
def _g8_risk_ok(self, risk: RiskSnapshot, intended_risk_r: float) -> GateResult: ...
```

`all_passed = all(g.passed for g in results.values())`.

**Testy:**

- Test each gate individually: passing and failing conditions.
- Test all-pass scenario.
- Test single-gate failure → overall fail.

-----

### 8.3 `signals/score_normalizer.py`

**Cel:** Normalizacja raw feature values do 0–1 per scoring component (sekcja 19.1 blueprintu).

**Interfejs:**

```python
class ScoreNormalizer:
    def normalize_sweep_quality(self, zscore: float, return_ratio: float) -> float: ...
    def normalize_return_quality(self, fts: float, failure_time_ms: int, max_ms: int) -> float: ...
    def normalize_absorption(self, absorption: float, exhaustion: float) -> float: ...
    def normalize_obi_ofi_reversal(self, ofi_magnitude: float, ofi_range: float) -> float: ...
    def normalize_lad(self, lad_imbalance: float, aligned: bool) -> float: ...
    def normalize_fair_value(self, target_bps: float) -> float: ...
    def normalize_binance_nonconfirm(self, degree: float) -> float: ...
    def normalize_liquidation(self, burst_score: float) -> float: ...
    def normalize_market_quality(self, dq: float, lat: float, spread_stab: float) -> float: ...
```

Każda metoda implementuje formułę z tabeli 19.1 blueprintu.

**Testy:**

- Test each normalizer: boundary values (0, 1, edge cases).
- Test clamping (output always in [0, 1]).

-----

### 8.4 `signals/scorer.py`

**Cel:** Composite scoring 0–100 z weighted components.

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    components: dict[str, float]     # component_name → normalized 0–1
    weighted: dict[str, float]       # component_name → weighted contribution
    total: float                     # 0–100
    risk_tier: str                   # "no_trade" | "half_risk" | "base_risk" | "max_risk"

class Scorer:
    def __init__(self, config: HardGatesConfig, normalizer: ScoreNormalizer): ...
    def score(self, features: MicrostructureFeatures, direction: Direction) -> ScoreBreakdown: ...
```

**Logika:**

1. Normalize each component.
1. Multiply by weight.
1. Sum = `score_total`.
1. Map to risk tier:
- < 72 → `no_trade`
- 72–79 → `half_risk`
- 80–87 → `base_risk`
- = 88 → `max_risk`

**Testy:**

- Test weight sum = 100.
- Test risk tier thresholds.
- Test known feature set → known score.

-----

### 8.5 `signals/long_setup.py` / `signals/short_setup.py`

**Cel:** Setup-specific logic z sekcji 17 blueprintu.

**Interfejs:**

```python
class LongSetup:
    def evaluate(
        self,
        features: MicrostructureFeatures,
        regime: RegimeState,
        session_ctx: SessionContext,
    ) -> bool:
        """Returns True if long setup conditions are met.""" ...

class ShortSetup:
    def evaluate(self, features: MicrostructureFeatures, ...) -> bool: ...
```

**Logika (Long):**

1. `sweep_side == "sell"` (sweep downward).
1. `sweep_level_type` is bottom-type (prior_low, val, poc, lvn_edge, failed_auction).
1. `reentry_into_range == True`.
1. `absorption_score >= 0.5` OR `exhaustion_score >= 0.5`.
1. OFI flip: `bybit_ofi_top10_1s > 0` (positive = buy pressure).
1. Microprice shift: `bybit_microprice_offset_bps > 0` (above mid).
1. Binance non-confirmation: `binance_ofi_top10_1s` not strongly negative.

Short = mirror all conditions.

**Testy:**

- Test each condition individually.
- Test full setup pass/fail.

-----

### 8.6 `signals/signal_router.py`

**Cel:** Orchestration: setup detection → gates → scoring → `SignalDecision`.

**Interfejs:**

```python
class SignalRouter:
    def __init__(
        self,
        long_setup: LongSetup,
        short_setup: ShortSetup,
        hard_gates: HardGates,
        scorer: Scorer,
        config: AppConfig,
    ): ...

    def evaluate(
        self,
        symbol: str,
        features: MicrostructureFeatures,
        regime: RegimeState,
        session_ctx: SessionContext,
        risk_snapshot: RiskSnapshot,
        book_valid_bybit: bool,
        book_valid_binance: bool,
        private_ws_alive: bool,
        ts_ms: int,
    ) -> SignalDecision: ...
```

**Logika:**

1. Check long setup → if True, `direction = LONG`.
1. Check short setup → if True, `direction = SHORT`.
1. If both True (shouldn’t happen but guard) → skip.
1. If neither → `direction = NONE`.
1. If direction != NONE:
- Run hard gates.
- If all pass: score.
- Build `SignalDecision`.
1. Log signal decision (all fields).

**Testy:**

- Test routing logic.
- Test gate failure → direction = NONE in decision.
- Test score determination.

-----

### 8.7 Acceptance gate — Faza 4

System musi:

1. Na każdym tick evaluować setup conditions.
1. Generować `SignalDecision` z poprawnym `hard_gates_detail`.
1. Score poprawnie weighted (sum = 100).
1. Risk tier poprawnie assigned.
1. Logować every signal decision (including NONE) do JSON lines.

**Test integration — Faza 4:**

Replay known scenarios (manually annotated) → verify:

- True positive sweep detection → signal generated.
- Breakout scenario → no signal.
- Wrong regime → gate blocked.
- Score within expected range for known features.

-----

## 9. Faza 5 — Execution

### 9.1 Cel

Execution FSM, order routing, SL/TP management. System potrafi wystawić zlecenie, śledzić jego lifecycle, zarządzać pozycją.

### 9.1.1 Kolejność implementacji

```
execution/venue_constraints.py
execution/order_validator.py
execution/stale_signal_guard.py
execution/order_router.py
execution/fill_tracker.py
execution/sl_tp_manager.py
execution/execution_fsm.py
```

-----

### 9.2 `execution/venue_constraints.py`

**Cel:** Wrapper on instrument metadata dla execution validation.

**Interfejs:**

```python
class VenueConstraints:
    def __init__(self, instrument_loader: InstrumentLoader): ...
    def validate_price(self, symbol: str, price: Decimal) -> bool: ...
    def validate_qty(self, symbol: str, qty: Decimal) -> bool: ...
    def floor_qty(self, symbol: str, qty: Decimal) -> Decimal: ...
    def round_price(self, symbol: str, price: Decimal) -> Decimal: ...
    def max_market_qty(self, symbol: str) -> Decimal: ...
```

-----

### 9.3 `execution/order_validator.py`

**Cel:** Pre-flight order validation.

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class ValidationResult:
    is_valid: bool
    errors: list[str]

class OrderValidator:
    def __init__(self, constraints: VenueConstraints): ...
    def validate(self, intent: ExecutionIntent) -> ValidationResult: ...
```

**Checks:**

1. `qty >= min_order_qty`.
1. `qty <= max_order_qty` (or `max_mkt_order_qty` for aggressive).
1. `price` within `[min_price, max_price]`.
1. `price` aligned to `tick_size`.
1. `qty` aligned to `qty_step`.
1. Leverage check: `qty * price / equity <= max_leverage`.

-----

### 9.4 `execution/stale_signal_guard.py`

**Cel:** Sprawdzanie czy signal jest still valid based on age.

**Interfejs:**

```python
class StaleSignalGuard:
    def __init__(self, config: ExecutionConfig): ...
    def is_signal_alive(self, signal: SignalDecision, current_ts_ms: int) -> bool: ...
    def is_passive_window_open(self, signal: SignalDecision, current_ts_ms: int) -> bool: ...
    def is_aggressive_window_open(self, signal: SignalDecision, current_ts_ms: int) -> bool: ...
    def signal_age_ms(self, signal: SignalDecision, current_ts_ms: int) -> int: ...
```

**Logika:**

- `signal_age = current_ts_ms - signal.ts_ms`.
- `is_signal_alive = signal_age < max_signal_age_ms` (config: 2000 ms).
- `is_passive_window_open = signal_age < passive_ttl_ms` (config: 500 ms).
- `is_aggressive_window_open = signal_age < aggressive_max_signal_age_ms` (config: 1200 ms).

-----

### 9.5 `execution/order_router.py`

**Cel:** Wysyłanie zleceń na Bybit via REST + tracking via WS.

**Interfejs:**

```python
class OrderRouter:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str,
        private_ws: BybitPrivateWS,
        validator: OrderValidator,
    ): ...
    async def submit_limit(self, symbol: str, side: str, price: Decimal, qty: Decimal, post_only: bool = True) -> str:
        """Returns orderId. Raises on validation failure.""" ...
    async def submit_market(self, symbol: str, side: str, qty: Decimal) -> str: ...
    async def cancel_order(self, symbol: str, order_id: str) -> bool: ...
    async def cancel_all(self, symbol: str) -> int:
        """Returns number of orders cancelled.""" ...
    async def amend_order(self, symbol: str, order_id: str, price: Decimal | None = None, qty: Decimal | None = None) -> bool: ...
```

**Logika:**

1. Validate via `OrderValidator`.
1. Sign request (HMAC-SHA256).
1. `POST /v5/order/create` with appropriate params.
1. Parse REST response → orderId.
1. REST ack = acceptance only. True state comes from WS (handled by FSM).

**Auth signing:**

```python
import hmac
import hashlib
import time

def sign_request(api_key: str, api_secret: str, params: dict) -> dict:
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"
    param_str = timestamp + api_key + recv_window + json.dumps(params)
    signature = hmac.new(api_secret.encode(), param_str.encode(), hashlib.sha256).hexdigest()
    return {"X-BAPI-SIGN": signature, "X-BAPI-API-KEY": api_key, "X-BAPI-TIMESTAMP": timestamp, "X-BAPI-RECV-WINDOW": recv_window}
```

-----

### 9.6 `execution/fill_tracker.py`

**Cel:** Track order fills z private WS updates.

**Interfejs:**

```python
@dataclass(slots=True)
class OrderState:
    order_id: str
    order_link_id: str
    symbol: str
    side: str
    status: OrderStatus
    price: Decimal | None
    qty: Decimal
    filled_qty: Decimal
    avg_fill_price: Decimal | None
    cumulative_fee: Decimal
    created_ts_ms: int
    last_update_ts_ms: int

class FillTracker:
    def __init__(self): ...
    def on_order_event(self, event: OrderEvent) -> None: ...
    def get_order(self, order_id: str) -> OrderState | None: ...
    def get_pending_orders(self, symbol: str) -> list[OrderState]: ...
    def get_filled_orders(self, symbol: str) -> list[OrderState]: ...
    @property
    def has_pending(self) -> bool: ...
```

-----

### 9.7 `execution/sl_tp_manager.py`

**Cel:** Stop Loss i Take Profit computation i management.

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class ExitLevels:
    stop_price: Decimal
    tp1_price: Decimal
    tp2_price: Decimal
    tp3_price: Decimal
    tp1_qty_pct: float   # 0.35
    tp2_qty_pct: float   # 0.40
    tp3_qty_pct: float   # 0.25

class SLTPManager:
    def __init__(
        self,
        config: ExitConfig,
        constraints: VenueConstraints,
    ): ...

    def compute_exit_levels(
        self,
        direction: Direction,
        entry_price: Decimal,
        sweep_extreme: Decimal,
        noise_floor: float,
        short_atr: float,
        tick_size: Decimal,
        session_ctx: SessionContext,
        vwap_engine: VwapEngine,
    ) -> ExitLevels: ...

    def should_move_stop_to_be(
        self,
        direction: Direction,
        entry_price: Decimal,
        current_price: float,
        tp1_hit: bool,
        flow_supportive: bool,
        round_trip_cost_bps: float,
    ) -> Decimal | None: ...

    def check_time_stop(
        self,
        position_age_ms: int,
        max_hold_time_ms: int,
        ofi_adverse: bool,
        adverse_excursion_pct: float,
    ) -> bool: ...
```

**Stop loss computation (sekcja 22.1 blueprintu):**

```python
buffer_ticks = max(2, noise_floor, short_atr * 0.3 / tick_size)
if direction == LONG:
    stop = sweep_extreme - (buffer_ticks * tick_size)
else:
    stop = sweep_extreme + (buffer_ticks * tick_size)
stop = round_to_tick(stop, tick_size)
```

**TP computation (sekcja 22.2 blueprintu):**

- TP validation: each TP must be >= `min_net_target_bps + costs`. If not → merge with previous TP.

-----

### 9.8 `execution/execution_fsm.py`

**Cel:** Full execution state machine (sekcja 21 blueprintu).

**Interfejs:**

```python
class ExecutionFSM:
    def __init__(
        self,
        symbol: str,
        order_router: OrderRouter,
        fill_tracker: FillTracker,
        sl_tp_manager: SLTPManager,
        stale_guard: StaleSignalGuard,
        config: ExecutionConfig,
    ): ...

    @property
    def state(self) -> ExecutionState: ...

    async def on_signal(self, signal: SignalDecision, intent: ExecutionIntent) -> None: ...
    async def on_order_event(self, event: OrderEvent) -> None: ...
    async def on_tick(self, ts_ms: int, features: MicrostructureFeatures) -> None: ...
    async def abort(self, reason: str) -> None: ...
    async def force_close(self, reason: str) -> None: ...
```

**Logika:**

Implementacja kompletnego state machine z sekcji 21.2 blueprintu.

Każde przejście jest jawnie zdefiniowane z warunkami.

**on_tick:** Called every 100 ms. Checks:

- In pre-fill states: abort conditions (sekcja 21.3).
- In POSITION_OPEN/MANAGE_EXIT: time stop, TP proximity, adverse excursion.
- In WAIT_PASSIVE_FILL: TTL expired → transition to PASSIVE_REPRICE or SUBMIT_AGGRESSIVE.

**Abort conditions (pre-fill):**

```python
def _check_abort_conditions(self, ts_ms: int, features: MicrostructureFeatures) -> str | None:
    if not self._stale_guard.is_signal_alive(self._signal, ts_ms):
        return "signal_stale"
    if features.spread_pctl > 95:
        return "spread_explosion"
    if features.depth_stability_score < 0.4:
        return "depth_collapse"
    if not self._private_ws_alive:
        return "private_ws_dead"
    # ... more conditions from blueprint
    return None
```

**State machine logging:**

Każde przejście stanu logowane z: `from_state`, `to_state`, `trigger`, `ts_ms`.

**Testy:**

- Test each state transition.
- Test abort conditions trigger correctly.
- Test full lifecycle: signal → passive → fill → manage → TP → close.
- Test passive timeout → aggressive fallback.
- Test passive timeout → abort (signal stale).

-----

### 9.9 Acceptance gate — Faza 5

System musi:

1. Walidować zlecenia vs instrument metadata.
1. Wysyłać PostOnly limit orders na Bybit demo.
1. Śledzić order lifecycle via private WS.
1. Obsługiwać passive → reprice → aggressive ladder.
1. Abortować na stale signal.
1. Liczyć SL/TP poprawnie.
1. Obsługiwać partial exits (TP1 → move stop → TP2 → TP3).
1. Time stop exit.

**Test integration — Faza 5:**

Manual trigger: wymuś sygnał z mock features → FSM przechodzi pełny lifecycle na demo account.

-----

## 10. Faza 6 — Risk

### 10.1 Cel

Position sizing, risk FSM, degraded mode, kill switch, cluster exposure, daily limits. System potrafi zarządzać ryzykiem, ograniczać ekspozycję, i wyłączać się w kryzysie.

### 10.1.1 Kolejność implementacji

```
risk/position_sizer.py
risk/correlation_bucket.py
risk/daily_limits.py
risk/degraded_mode.py
risk/kill_switch.py
risk/risk_fsm.py
risk/risk_engine.py
```

-----

### 10.2 `risk/position_sizer.py`

**Cel:** Position sizing z sekcji 26 blueprintu.

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class SizingResult:
    qty: Decimal
    notional_usd: float
    risk_usd: float
    risk_pct: float
    effective_leverage: float
    was_leverage_capped: bool
    is_viable: bool      # False if leverage cap makes risk < min_viable

class PositionSizer:
    def __init__(self, config: RiskConfig, constraints: VenueConstraints): ...
    def compute(
        self,
        symbol: str,
        equity: float,
        risk_pct: float,
        entry_price: Decimal,
        stop_price: Decimal,
    ) -> SizingResult: ...
```

**Logika:**

Implementacja sekcji 26.1–26.3 blueprintu:

1. `risk_usd = equity * risk_pct`.
1. `stop_distance = abs(entry - stop)`.
1. `qty_raw = risk_usd / stop_distance`.
1. `qty = floor_to_step(qty_raw, qty_step)`.
1. Leverage check: if `qty * entry / equity > max_leverage` → reduce qty.
1. If reduced qty yields risk < `min_viable_risk_pct` → `is_viable = False`.
1. Clamp to min/max qty, max market qty.

**Testy:**

- Test normal sizing.
- Test leverage cap kicks in.
- Test non-viable (too tight stop).
- Test qty step alignment.

-----

### 10.3 `risk/correlation_bucket.py`

**Cel:** Tracking cluster exposure (sekcja 23.1 blueprintu).

**Interfejs:**

```python
class CorrelationBucket:
    def __init__(self, cap_r: float = 1.5): ...
    def add_position(self, symbol: str, risk_r: float) -> None: ...
    def remove_position(self, symbol: str) -> None: ...
    def current_exposure_r(self) -> float: ...
    def can_add(self, additional_risk_r: float) -> bool: ...
```

-----

### 10.4 `risk/daily_limits.py`

**Cel:** Daily PnL tracking i stop logic.

**Interfejs:**

```python
class DailyLimits:
    def __init__(self, config: RiskConfig): ...
    def update_pnl(self, pnl_pct: float) -> None: ...
    def reset(self) -> None:  # called at 00:00 UTC
    @property
    def daily_pnl_pct(self) -> float: ...
    @property
    def is_soft_stop(self) -> bool: ...
    @property
    def is_hard_stop(self) -> bool: ...
```

-----

### 10.5 `risk/degraded_mode.py`

**Cel:** Venue quality state management (sekcja 25 blueprintu).

**Interfejs:**

```python
class DegradedModeManager:
    def __init__(self): ...
    def update_venue_state(self, health: HealthStatus) -> VenueHealthState: ...
    def is_trading_allowed(self) -> bool: ...
    def get_restrictions(self) -> dict[str, bool]: ...
```

**Logika:**

Mapowanie `HealthStatus` → `VenueHealthState` + restrictions per state (tabela z sekcji 25.2 blueprintu).

-----

### 10.6 `risk/kill_switch.py`

**Cel:** Emergency stop (sekcja 24.3 blueprintu, ANY → KILL_SWITCH triggery).

**Interfejs:**

```python
class KillSwitch:
    def __init__(self, shutdown: GracefulShutdown): ...
    def check_triggers(
        self,
        private_ws_alive: bool,
        private_ws_last_heartbeat_ms: int,
        order_desync_detected: bool,
        reject_count_5min: int,
        ntp_drift_ms: float,
        maintenance_imminent: bool,
    ) -> bool:
        """Returns True if KILL_SWITCH should activate.""" ...
    async def activate(self, reason: str) -> None: ...
```

**Triggery:**

- `private_ws_alive == False` and last heartbeat > 30 s ago.
- `order_desync_detected == True`.
- `reject_count_5min > 5`.
- `ntp_drift_ms > 2000`.
- `maintenance_imminent == True`.

-----

### 10.7 `risk/risk_fsm.py`

**Cel:** Risk state machine (sekcja 24 blueprintu).

**Interfejs:**

```python
class RiskFSM:
    def __init__(self, config: RiskConfig): ...

    @property
    def state(self) -> RiskState: ...

    def evaluate_transition(
        self,
        daily_pnl_pct: float,
        consecutive_losses: int,
        consecutive_losses_this_setup: int,
        data_quality: float,
        vol_ratio: float,
        private_ws_stable: bool,
        feed_issues: bool,
        kill_switch_triggered: bool,
        cooldown_elapsed: bool,
    ) -> RiskState: ...

    def get_allowed_risk_pct(self, base_risk: float, score_tier: str) -> float: ...
    def apply_risk_modifiers(
        self,
        risk_pct: float,
        spread_pctl: float,
        depth_stability: float,
        score: float,
        data_quality: float,
        cluster_exposure_r: float,
        cluster_cap_r: float,
        vol_ratio: float,
    ) -> float: ...
```

**Logika:**

Implementacja kompletnego state machine z sekcji 24.2–24.3. Risk modifiers z sekcji 23.4.

-----

### 10.8 `risk/risk_engine.py`

**Cel:** Top-level risk orchestrator. Buduje `RiskSnapshot`.

**Interfejs:**

```python
class RiskEngine:
    def __init__(
        self,
        config: RiskConfig,
        fsm: RiskFSM,
        sizer: PositionSizer,
        bucket: CorrelationBucket,
        daily: DailyLimits,
        degraded: DegradedModeManager,
        kill_switch: KillSwitch,
    ): ...

    def get_snapshot(self) -> RiskSnapshot: ...
    def compute_intent(
        self,
        signal: SignalDecision,
        score_breakdown: ScoreBreakdown,
        features: MicrostructureFeatures,
        session_ctx: SessionContext,
        vol_engine: VolatilityEngine,
        vwap_engine: VwapEngine,
        entry_price: Decimal,
        sweep_extreme: Decimal,
        equity: float,
    ) -> ExecutionIntent | None:
        """Returns None if risk prevents trade.""" ...
```

**Logika:**

1. Check risk state (FSM).
1. Determine risk_pct based on score tier + state.
1. Apply risk modifiers.
1. Compute position size.
1. Compute SL/TP.
1. Validate cluster exposure.
1. Build `ExecutionIntent` or return None.

-----

### 10.9 Acceptance gate — Faza 6

System musi:

1. Sizować pozycje poprawnie (z leverage cap).
1. Trackować cluster exposure.
1. Przechodzić między stanami risk FSM (NORMAL → REDUCED → PAUSED → KILL_SWITCH).
1. Aplikować risk modifiers (obniżać risk przy adverse conditions).
1. Respektować daily limits (soft/hard stop).
1. Aktywować KILL_SWITCH na trigger conditions.
1. Blokować trading w degraded venue state.

-----

## 11. Faza 7 — Replay & Validation

### 11.1 Cel

Event replay engine, fill simulator, walk-forward testing, acceptance criteria validation. System potrafi odtwarzać historyczne dane i weryfikować strategię.

### 11.1.1 Kolejność implementacji

```
replay/event_replay.py
replay/book_replay.py
replay/fill_simulator.py
replay/walk_forward.py
replay/metrics.py
```

-----

### 11.2 `replay/event_replay.py`

**Cel:** Odczytywanie raw events z Parquet i odtwarzanie ich w kolejności czasowej.

**Interfejs:**

```python
class EventReplay:
    def __init__(self, data_dir: str, start_date: str, end_date: str, symbols: list[str]): ...
    def __aiter__(self) -> AsyncIterator[MarketEvent]: ...
    async def replay(self, callback: Callable[[MarketEvent], Awaitable[None]]) -> None: ...
    @property
    def event_count(self) -> int: ...
```

**Logika:**

- Read Parquet files chronologically.
- Merge-sort events from multiple venues/symbols by `exchange_ts_ms`.
- Yield events in order.

-----

### 11.3 `replay/fill_simulator.py`

**Cel:** Symulacja fill’i w replay (nie ma real exchange).

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class SimulatedFill:
    price: Decimal
    qty: Decimal
    fee: Decimal
    slippage_ticks: int
    fill_type: str   # "maker" | "taker"
    latency_ms: int

class FillSimulator:
    def __init__(
        self,
        maker_fee_bps: float = 1.0,
        taker_fee_bps: float = 5.5,
        simulated_latency_ms: int = 50,
    ): ...

    def simulate_passive_fill(
        self,
        order_price: Decimal,
        order_qty: Decimal,
        book_state: OrderBookState,
        trades_since_order: list[TradeEvent],
    ) -> SimulatedFill | None:
        """Returns fill if market traded through order price. Models queue position.""" ...

    def simulate_aggressive_fill(
        self,
        order_qty: Decimal,
        book_state: OrderBookState,
    ) -> SimulatedFill:
        """Walk the book to estimate fill price and slippage.""" ...
```

**Passive fill model:**

- Order enters queue at back.
- Fill occurs when cumulative volume at order price >= estimated queue ahead + order qty.
- Queue ahead estimated as: visible depth at order price at time of submission * position factor (0.5 = middle of queue assumption).

**Aggressive fill model:**

- Walk through book levels consuming liquidity.
- `avg_fill_price = sum(level_price * min(remaining_qty, level_size)) / total_qty`.
- Slippage = `(avg_fill_price - best_price) / tick_size`.

-----

### 11.4 `replay/walk_forward.py`

**Cel:** Walk-forward backtesting engine.

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class WalkForwardConfig:
    train_days: int = 30
    test_days: int = 14
    step_days: int = 14

class WalkForwardEngine:
    def __init__(self, config: WalkForwardConfig, data_dir: str): ...
    async def run(self, symbols: list[str]) -> list[WindowResult]: ...
```

**Logika:**

1. Divide data into overlapping train/test windows.
1. For each window: run full replay (same code path as live).
1. Collect per-window metrics.
1. Validate acceptance criteria per window.

-----

### 11.5 `replay/metrics.py`

**Cel:** Obliczanie performance metrics.

**Interfejs:**

```python
@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    total_trades: int
    win_rate: float
    avg_rr: float
    net_expectancy_per_trade: float
    gross_pnl_pct: float
    net_pnl_pct: float
    max_drawdown_pct: float
    max_daily_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    avg_hold_time_ms: int
    median_slippage_passive_ticks: float
    median_slippage_aggressive_ticks: float
    pct_positive_2week_windows: float

class MetricsCalculator:
    def __init__(self): ...
    def add_trade(self, trade_result: TradeResult) -> None: ...
    def compute(self) -> PerformanceMetrics: ...
    def check_acceptance(self) -> tuple[bool, list[str]]:
        """Returns (passed, list of failed criteria).""" ...
```

**Acceptance criteria (sekcja 29.2 blueprintu):**

```python
def check_acceptance(self) -> tuple[bool, list[str]]:
    failures = []
    m = self.compute()
    if m.net_expectancy_per_trade <= 0:
        failures.append("net_expectancy <= 0")
    if m.pct_positive_2week_windows < 0.60:
        failures.append(f"positive_windows {m.pct_positive_2week_windows} < 0.60")
    if m.max_daily_drawdown_pct > 1.5:
        failures.append(f"daily_dd {m.max_daily_drawdown_pct} > 1.5%")
    if m.max_drawdown_pct > 5.0:
        failures.append(f"total_dd {m.max_drawdown_pct} > 5%")
    if m.median_slippage_passive_ticks > 1.5:
        failures.append(f"passive_slip {m.median_slippage_passive_ticks} > 1.5")
    if m.median_slippage_aggressive_ticks > 3.0:
        failures.append(f"aggressive_slip {m.median_slippage_aggressive_ticks} > 3.0")
    return (len(failures) == 0, failures)
```

-----

### 11.6 Acceptance gate — Faza 7

1. Event replay odtwarza data poprawnie (chronological order, all events).
1. Fill simulator produces realistic fills (queue model + book walking).
1. Walk-forward engine runs complete test periods.
1. Metrics accurately computed.
1. Acceptance criteria correctly evaluated.

-----

## 12. Faza 8 — Demo Forward

### 12.1 Cel

Live demo trading — system działa na Bybit demo z real market data. Walidacja, że live behavior matches replay expectations.

### 12.1.1 Sequence

**Stage 1: BTC only (2+ tygodnie)**

- Enable only BTCUSDT.
- Run 24/7 (active during session windows, passive outside).
- Monitor: signal count, fill rate, slippage, PnL.
- Acceptance: net expectancy > 0, daily DD < 1.5%.

**Stage 2: ETH only (2+ tygodnie)**

- Same criteria as BTC.

**Stage 3: SOL only (2+ tygodnie)**

- Same criteria. SOL may have worse fill quality due to lower liquidity — monitor closely.

**Stage 4: All three concurrent (2+ tygodnie)**

- Full system with cluster exposure management.
- Monitor cross-symbol interaction.
- Acceptance: full acceptance criteria from sekcja 29.2.

### 12.2 Demo validation checklist

Per stage, validate:

- Signal directions match replay expectations (± 20% fill rate tolerance).
- Execution FSM transitions are clean (no stuck states, no ERROR states).
- Risk FSM transitions are correct (REDUCED triggers at right moments).
- WS reconnects handled gracefully (< 3 reconnects per day average).
- Logging completeness: every trade has full audit trail.
- Shutdown/restart: system resumes correctly after restart.

### 12.3 Replay vs Demo comparison

After demo period, run replay on same time period with recorded data:

1. Compare signal timestamps and directions.
1. Compare fill rates (demo vs replay simulator).
1. If demo fill rate differs > 20% from replay → investigate fill model calibration.
1. If directional mismatch > 10% of signals → investigate feature/context divergence.

-----

## 13. Cross-cutting concerns

### 13.1 Logging architecture

Wszystkie moduły używają `structlog` z JSON output:

```python
import structlog

logger = structlog.get_logger()

logger.info("order_submitted", symbol="BTCUSDT", side="Buy", price="98500.50", qty="0.001")
```

Log levels:

- `DEBUG`: feature values, every tick state.
- `INFO`: signals, orders, fills, state transitions.
- `WARNING`: degraded states, reconnects, near-threshold values.
- `ERROR`: failed operations, validation failures.
- `CRITICAL`: KILL_SWITCH, unrecoverable errors.

### 13.2 Monitoring dashboard

`monitoring/dashboard.py` — terminal-based (Rich) dashboard showing:

- Per-symbol: current price, regime, book health, feature highlights.
- Global: risk state, daily PnL, open positions, pending orders.
- Alerts: recent warnings/errors.
- Latency: per-venue median/p99.

### 13.3 Alerting

`monitoring/alerts.py`:

- `SESSION_DRIFT` — volume outside windows.
- `RECONNECT_STORM` — excessive reconnects.
- `LATENCY_SPIKE` — p99 > threshold.
- `REGIME_MISMATCH` — trade loss in wrong regime.
- `FILL_QUALITY_DEGRADATION` — slippage exceeding expectations.

### 13.4 Config versioning

Każdy config file ma `config_version`. Boot loguje full config snapshot. Config changes require restart + new version. Git tracks all config changes.

### 13.5 Data retention

- Raw events: 90 days.
- Feature snapshots: 90 days.
- Signal decisions: indefinitely.
- Trade logs: indefinitely.
- Order logs: indefinitely.
- Health events: 30 days.

Rotation/cleanup: daily cron job or startup task.

-----

## 14. Acceptance gates między fazami

|Faza    |Gate                                                      |Kto validuje      |
|--------|----------------------------------------------------------|------------------|
|0 → 1   |`make all-checks` passes, core types correct              |Automated         |
|1 → 2   |60s live data: books valid, logging works, reconnect works|Manual + automated|
|2 → 3   |1 day replay: VWAP, POC, regime match manual annotations  |Manual + automated|
|3 → 4   |1 day replay: features complete, sweep detection TPR > 0.8|Manual + automated|
|4 → 5   |Known scenarios: correct signals generated, gates work    |Automated         |
|5 → 6   |Demo: full order lifecycle works on Bybit demo            |Manual            |
|6 → 7   |Demo: risk FSM transitions correct, sizing accurate       |Manual + automated|
|7 → 8   |Walk-forward: acceptance criteria pass on historical data |Automated         |
|8 → Live|8+ weeks demo: all acceptance criteria pass per stage     |Manual            |

-----

## 15. Checklist końcowy

Przed przejściem do produkcji:

- [ ] Wszystkie 12 reguł końcowych z blueprintu zaimplementowane i testowane.
- [ ] Config version matches blueprint version.
- [ ] mypy –strict passes z zero errors.
- [ ] Test coverage > 85% overall, > 95% na core/signals/execution/risk.
- [ ] Walk-forward acceptance criteria pass na minimum 3 miesiącach danych.
- [ ] Demo forward acceptance criteria pass na minimum 8 tygodniach.
- [ ] Graceful shutdown tested: SIGTERM, KILL_SWITCH, unrecoverable error.
- [ ] WS reconnect tested: manual disconnect each WS → verify recovery.
- [ ] Clock drift tested: inject NTP offset → verify KILL_SWITCH triggers.
- [ ] Metadata staleness tested: block refresh → verify trading stops.
- [ ] Full audit trail verified: every demo trade has complete log chain.
- [ ] Replay vs demo comparison: < 20% fill rate divergence, < 10% signal mismatch.
- [ ] Dashboard operational: all metrics visible.
- [ ] Alerting operational: all alert types tested.
- [ ] Documentation: README, deployment guide, operational runbook.
- [ ] Security: API keys in env vars, not in config files. `.env` in `.gitignore`.