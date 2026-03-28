# VOLF HYPER APEX 2026

## Production Blueprint

**Crypto Futures Perpetual Mean-Reversion Engine**
**Bybit Execution + Bybit/Binance Market Data**

Config version: `blueprint-2.0.0`
Aktualne na: 2026-03-28

-----

## 1. Cel projektu

Celem systemu jest wyspecjalizowany intraday engine do handlu:

- tylko na BTCUSDT, ETHUSDT, SOLUSDT,
- tylko na futures perpetual,
- tylko w logice mean reversion po failed liquidity grab,
- tylko wtedy, gdy:
  - istnieje wcześniej zmapowane miejsce płynności / value,
  - sweep zostaje odrzucony,
  - order flow potwierdza failure continuation,
  - execution nadal ma sens netto po kosztach.

System nie jest botem od wszystkiego.
To ma być wąski, brutalnie selektywny engine z naciskiem na:

1. net expectancy po kosztach,
1. stabilność,
1. niski drawdown,
1. execution realism,
1. odporność operacyjną.

-----

## 2. Założenia nadrzędne

### 2.1 Co jest edge

Edge nie wynika z pojedynczego wskaźnika.

Edge = połączenie 5 warstw:

1. context / value,
1. regime filter,
1. failed liquidity grab trigger,
1. microstructure confirmation,
1. dobre execution + twardy risk control.

### 2.2 Czego nie zakładamy

Nie zakładamy:

- magicznego 75–85% win rate,
- stałego RR 1:3 dla każdego trade’u,
- wallet-based smart money attribution jako core,
- RL jako głównego silnika entry,
- jednolitego „raw tick-by-tick cross-exchange booka” z public feeds.

Publiczny stack danych narzuca ograniczenia: Binance futures aggTrade agreguje fill’e co 100 ms, a Bybit public orderbook i trade mają własne kadencje i formaty. Dlatego projekt opiera się na venue-native event processing + kanoniczny zegar 100 ms, zamiast udawania czystego HFT.

### 2.3 Precision policy

Wszystkie wartości cenowe i ilościowe wewnątrz systemu operują na `Decimal` (Python `decimal.Decimal`) lub int z fixed-point. Nie używamy `float` do porównań cenowych, walidacji ticków ani logiki orderów. `float` dopuszczalny jest wyłącznie w feature engineeringu (OBI, OFI, score), gdzie epsilonowe rozbieżności nie mają wpływu na execution.

-----

## 3. Exchange model

### 3.1 Role giełd

**Bybit:**

- execution venue,
- główny venue triggerów microstructure,
- główne źródło prawdy o fillach i statusach orderów.

**Binance:**

- secondary context venue,
- dodatkowe potwierdzenie lub brak potwierdzenia continuation,
- referencyjna warstwa flow / depth dla cross-venue sanity check.

### 3.2 Demo environment

Tryb testowy:

- private trading przez `https://api-demo.bybit.com`,
- private websocket przez `wss://stream-demo.bybit.com`,
- public market data jest taka sama jak mainnetowa i nie idzie z demo WS,
- demo ma własny user ID i własne klucze,
- demo ma defaultowe, niepodnoszalne limity,
- zlecenia demo są trzymane przez 7 dni.

-----

## 4. Instrument universe

Na start: BTCUSDT, ETHUSDT, SOLUSDT.

Jeden silnik dla wszystkich, ale żaden próg nie może być sztywny w USD lub tickach bez normalizacji.

Każdy próg ma być liczony jako:

- rolling percentyl,
- rolling z-score,
- lub relacja do lokalnego noise floor / ATR short-term / tick value.

Dotyczy to również spread thresholds — `max_spread_ticks` w configu jest wartością startową, ale runtime musi walidować spread jako percentyl rolling distribution spreadu dla danego symbolu w aktywnej sesji.

-----

## 5. Krytyczne fakty implementacyjne

### 5.1 Binance market data

Binance USDⓈ-M:

- aggTrade = agregacja filli o tej samej cenie i tej samej stronie takera co 100 ms,
- local order book trzeba budować z:
  - websocket depth stream,
  - REST snapshot,
  - poprawnej walidacji U, u, pu, lastUpdateId,
  - jeśli `pu != previous_u`, trzeba robić pełny resync.

### 5.2 Bybit market data

Bybit public websocket:

- `publicTrade.{symbol}` = real-time trades,
- `orderbook.{depth}.{symbol}` = snapshot + delta,
- nowy snapshot oznacza reset lokalnej książki,
- dla linear:
  - level 50: 20 ms,
  - level 200: 100 ms,
  - level 1000: 200 ms,
- RPI orders nie są włączone do wiadomości orderbook.

### 5.3 Bybit execution

Bybit create-order:

- wspiera Limit, Market, PostOnly,
- market order jest w praktyce konwertowany przez silnik na IOC-limit z limitem poślizgu,
- samo potwierdzenie REST oznacza tylko przyjęcie requestu,
- prawdą o stanie ordera ma być websocket.

### 5.4 Instrument metadata

Na boot trzeba pobrać Get Instruments Info dla każdego symbolu i trzymać lokalnie:

- tickSize, minPrice, maxPrice,
- qtyStep, minOrderQty, maxOrderQty, maxMktOrderQty,
- priceScale,
- minLeverage, maxLeverage, leverageStep.

Bez tego execution nie może walidować zleceń poprawnie. Bybit udostępnia te dane w priceFilter, lotSizeFilter i leverageFilter.

Metadata refresh: co 4 godziny lub po każdym restarcie. Jeśli refresh się nie powiedzie, system wchodzi w METADATA_STALE i blokuje nowe zlecenia do czasu pomyślnego odświeżenia.

### 5.5 Rate limits

**Bybit:**

- HTTP IP default: 600 requests / 5 s / IP,
- websocket: nie więcej niż 500 połączeń w 5 minut,
- market data websocket: nie więcej niż 1000 połączeń / IP, liczone osobno per market type,
- nie wolno „thrashować” connect/disconnect.

**Binance:**

- należy pilnować limitów websocket i nie projektować architektury przez masowe rozdrabnianie połączeń. Oficjalne market stream docs są źródłem reguł połączeń i subskrypcji.

### 5.6 Bybit system status

System musi pollować Bybit Server Time / Announcement endpoint co 60 s celem wykrywania scheduled maintenance i incident announcements. Wykrycie maintenance window = przejście w SYSTEM_ABNORMAL i stop nowych wejść 5 minut przed planowaną przerwą.

-----

## 6. Architektura logiczna

System ma 10 warstw:

1. Boot & Metadata,
1. Market Data Ingestion,
1. Normalization & Local Book Reconstruction,
1. Context / Value / Regime,
1. Microstructure Feature Engine,
1. Signal Engine,
1. Execution Engine,
1. Risk Engine,
1. Storage / Replay / Monitoring,
1. Time Synchronization & Health.

-----

## 7. Runtime pipeline

```
BOOT
  -> load config (with version validation)
  -> validate environment
  -> NTP sync check
  -> fetch instrument metadata
  -> open public feeds (Bybit + Binance)
  -> open private Bybit demo trading feeds
  -> build local books
  -> start canonical clock (100ms)
  -> compute context
  -> compute features
  -> detect setup
  -> hard gates
  -> score
  -> execution intent
  -> order lifecycle via private WS
  -> position/risk management
  -> logging + replay + dashboard
```

-----

## 8. Time synchronization

### 8.1 NTP sync

System na boot i co 5 minut wykonuje NTP check. Mierzy offset lokalnego zegara vs serwer NTP.

### 8.2 Exchange clock drift

Porównujemy `recv_ts_ms - exchange_ts_ms` w rolling window (1000 eventów). Jeśli median drift > 500 ms lub p99 drift > 2000 ms, system loguje warning. Jeśli median drift > 2000 ms → KILL_SWITCH.

### 8.3 Canonical timestamp assignment

Każdy event dostaje:

- `exchange_ts_ms` — timestamp z venue,
- `recv_ts_ms` — moment odbioru przez system (monotonic clock),
- `canonical_ts_ms` — przypisanie do nearest 100 ms bucket na podstawie `recv_ts_ms`.

Feature snapshot jest budowany z eventów zatwierdzonych do danego canonical bucket. Event z `recv_ts_ms` spoza aktualnego bucketu nie może modyfikować snapshot z poprzedniego bucketu (no look-back mutation).

-----

## 9. Repo structure

```
volf_hyper_apex/
├── config/
│   ├── base.yaml           # config_version field required
│   ├── symbols.yaml
│   ├── sessions.yaml
│   ├── execution.yaml
│   ├── risk.yaml
│   └── venues.yaml
├── core/
│   ├── enums.py
│   ├── types.py             # Decimal-based Price, Qty types
│   ├── events.py
│   ├── clocks.py
│   ├── ids.py
│   ├── math.py
│   └── state.py
├── boot/
│   ├── instrument_loader.py
│   ├── environment_check.py
│   ├── venue_health.py
│   ├── ntp_sync.py
│   └── startup_validator.py
├── marketdata/
│   ├── bybit_public_ws.py
│   ├── bybit_private_ws.py
│   ├── binance_ws.py
│   ├── snapshot_fetcher.py
│   ├── normalizer.py
│   ├── local_book.py
│   ├── resync_manager.py
│   ├── ws_reconnect.py
│   └── canonical_clock.py
├── context/
│   ├── session_model.py
│   ├── value_profile.py
│   ├── vwap_engine.py
│   ├── regime_engine.py
│   ├── volatility_filters.py
│   ├── funding_oi_context.py
│   └── level_map.py
├── features/
│   ├── obi.py
│   ├── ofi.py
│   ├── microprice.py
│   ├── cvd.py
│   ├── lad.py
│   ├── sweep_detector.py
│   ├── absorption.py
│   ├── exhaustion.py
│   ├── replenishment.py
│   ├── spoof_probability.py
│   ├── iceberg_inference.py
│   ├── liquidation_burst.py
│   ├── trade_efficiency.py
│   └── feature_snapshot.py
├── signals/
│   ├── hard_gates.py
│   ├── scorer.py
│   ├── score_normalizer.py
│   ├── long_setup.py
│   ├── short_setup.py
│   └── signal_router.py
├── execution/
│   ├── order_validator.py
│   ├── order_router.py
│   ├── stale_signal_guard.py
│   ├── fill_tracker.py
│   ├── sl_tp_manager.py
│   ├── execution_fsm.py
│   └── venue_constraints.py
├── risk/
│   ├── position_sizer.py
│   ├── correlation_bucket.py
│   ├── daily_limits.py
│   ├── degraded_mode.py
│   ├── kill_switch.py
│   ├── risk_fsm.py
│   └── risk_engine.py
├── storage/
│   ├── raw_writer.py
│   ├── parquet_store.py
│   ├── feature_store.py
│   ├── order_log.py
│   └── trade_log.py
├── replay/
│   ├── event_replay.py
│   ├── book_replay.py
│   ├── fill_simulator.py
│   ├── walk_forward.py
│   └── metrics.py
├── monitoring/
│   ├── dashboard.py
│   ├── health.py
│   ├── latency.py
│   ├── alerts.py
│   ├── venue_status.py
│   └── system_status.py
├── shutdown/
│   └── graceful_shutdown.py
└── app.py
```

-----

## 10. Core classes

### 10.1 Event layer

```python
class MarketEvent:
    venue: str
    symbol: str
    exchange_ts_ms: int
    recv_ts_ms: int
    canonical_ts_ms: int
    event_type: str

class TradeEvent(MarketEvent):
    price: Decimal
    qty: Decimal
    notional: Decimal
    taker_side: str        # "buy" | "sell"
    seq: int | None

class BookDeltaEvent(MarketEvent):
    bids: list[tuple[Decimal, Decimal]]
    asks: list[tuple[Decimal, Decimal]]
    is_snapshot: bool
    update_id_from: int | None
    update_id_to: int | None

class OrderEvent:
    venue: str
    symbol: str
    order_id: str
    order_link_id: str | None
    status: str
    side: str
    price: Decimal | None
    qty: Decimal
    filled_qty: Decimal
    avg_fill_price: Decimal | None
    reject_reason: str | None
    ts_ms: int
```

### 10.2 Book layer

```python
class BookLevel:
    price: Decimal
    size: Decimal

class OrderBookState:
    venue: str
    symbol: str
    bids: list[BookLevel]
    asks: list[BookLevel]
    best_bid: Decimal
    best_ask: Decimal
    mid: float              # float ok — derived, not used for order logic
    spread_ticks: int
    last_update_ts_ms: int
    is_valid: bool
    last_snapshot_ts_ms: int
    update_count_since_snapshot: int

class LocalBookRebuilder:
    def apply_snapshot(self, event: BookDeltaEvent) -> None: ...
    def apply_delta(self, event: BookDeltaEvent) -> None: ...
    def get_state(self) -> OrderBookState: ...
    def is_consistent(self) -> bool: ...
    def reset(self) -> None: ...
    def staleness_ms(self) -> int: ...
```

### 10.3 Context layer

```python
class SessionContext:
    active_session: str     # "EU_OPEN" | "US_OVERLAP" | "FUNDING_ADJACENT" | "INACTIVE"
    session_vwap: float
    session_poc: float
    value_area_high: float
    value_area_low: float
    hvn_levels: list[float]
    lvn_levels: list[float]
    prior_high: float
    prior_low: float
    prior_poc: float
    prior_vah: float
    prior_val: float

class RegimeState:
    regime_name: str        # "BALANCED" | "ROTATIONAL" | "LOCAL_STRETCH" | "TREND_DAY" | "VOL_EXPANSION" | "INVALID"
    regime_confidence: float
    fair_value_anchor: float       # see section 14.8 for computation
    fair_value_distance_bps: float
    realized_vol_short: float      # rolling 5 min realized vol (annualized)
    realized_vol_baseline: float   # rolling 2 h realized vol (annualized)
```

### 10.4 Feature layer

```python
class MicrostructureFeatures:
    symbol: str
    ts_ms: int

    # Order book imbalance
    bybit_obi_5bp: float
    bybit_obi_10bp: float
    binance_obi_5bp: float
    binance_obi_10bp: float
    queue_imbalance_top1: float
    queue_imbalance_top3: float

    # Order flow imbalance
    bybit_ofi_top10_1s: float
    binance_ofi_top10_1s: float

    # Microprice
    bybit_microprice_offset_bps: float
    binance_microprice_offset_bps: float

    # Cumulative volume delta
    cvd_1s: float
    cvd_3s: float
    cvd_10s: float

    # Signed notional flow
    signed_notional_300ms: float
    signed_notional_1s: float
    trade_efficiency_score: float   # price impact per unit notional

    # Large Aggressor Delta
    lad_buy_1s: float
    lad_sell_1s: float
    lad_imbalance_1s: float
    lad_buy_count_3s: int
    lad_sell_count_3s: int

    # Sweep / failure
    sweep_detected: bool
    sweep_side: str                 # "buy" | "sell" | "none"
    sweep_distance_ticks: int
    sweep_distance_zscore: float
    sweep_level_type: str           # "prior_high" | "prior_low" | "vah" | "val" | "poc" | "lvn_edge" | "failed_auction"
    sweep_return_ratio: float
    sweep_failure_time_ms: int
    followthrough_failure_score: float
    reentry_into_range: bool

    # Confirmation
    absorption_score: float
    exhaustion_score: float
    replenishment_score: float
    level_hold_score: float
    iceberg_inference_score: float
    spoof_probability: float
    liquidation_burst_score: float

    # Market quality
    spread_ticks: int
    spread_pctl: float              # current spread as percentile of rolling session distribution
    spread_stability_score: float
    depth_stability_score: float
    book_update_rate: float         # updates/sec
    trade_update_rate: float        # trades/sec
    data_quality_score: float
    latency_score: float

    # Fair value features
    fair_value_distance_bps: float
    target_distance_bps: float
    session_vwap_distance_bps: float
    session_poc_distance_bps: float

    # Funding / OI context
    funding_rate: float | None
    funding_zscore: float | None
    oi_delta_5m: float | None
    oi_delta_5m_zscore: float | None
```

### 10.5 Signal / execution / risk layer

```python
class SignalDecision:
    symbol: str
    ts_ms: int
    direction: str              # "long" | "short" | "none"
    hard_gates_passed: bool
    hard_gates_detail: dict[str, bool]   # per-gate pass/fail
    score_total: float
    score_components: dict[str, float]   # raw 0–1 per component
    setup_name: str
    max_signal_age_ms: int

class ExecutionIntent:
    symbol: str
    direction: str
    entry_style: str            # "passive_first" | "aggressive_confirm" | "skip"
    entry_price: Decimal | None
    stop_price: Decimal
    tp_prices: list[Decimal]
    qty: Decimal
    size_usd: float
    validity_ms: int
    created_ts_ms: int          # timestamp of intent creation

class RiskSnapshot:
    equity: float
    daily_pnl_pct: float
    consecutive_losses: int
    consecutive_losses_this_setup: int
    cluster_exposure_r: float
    open_position_count: int
    risk_state: str             # "NORMAL" | "REDUCED" | "PAUSED_SETUP" | "PAUSED_STRATEGY" | "KILL_SWITCH"
```

-----

## 11. Boot layer

### 11.1 Boot sequence

1. Load config (validate `config_version` field).
1. Validate environment (Python version, dependencies, disk space).
1. NTP sync check — abort if offset > 2000 ms.
1. Fetch instrument metadata from Bybit.
1. Validate symbol support (all 3 symbols must be available).
1. Check Bybit system status endpoint — abort if maintenance < 15 min away.
1. Open public WS:
- Bybit orderbook,
- Bybit publicTrade,
- Binance aggTrade,
- Binance depth.
1. Open private Bybit demo streams.
1. Seed local books:
- Binance via REST snapshot + buffered diffs,
- Bybit via websocket snapshot.
1. Start health monitor.
1. Start canonical clock.
1. Enable signal engine dopiero gdy:
- metadata loaded,
- books valid,
- private WS alive,
- NTP offset acceptable,
- no degraded state blocking trading.

### 11.2 Instrument metadata cache

Dla każdego symbolu cache’ujemy:

- tick size, qty step,
- min/max price,
- min/max qty, max market qty,
- leverage range + step,
- price scale.

To jest obowiązkowe przed pierwszym orderem. Refresh co 4 godziny. Stale metadata (> 8h bez refresh) = METADATA_STALE → zero nowych zleceń.

-----

## 12. Market data layer

### 12.1 Bybit feeds

Subskrypcje:

- `orderbook.50.{symbol}` — execution-sensitive features (20 ms cadence),
- `orderbook.200.{symbol}` — szerszy context depth (100 ms cadence),
- `publicTrade.{symbol}` — real-time trades do signed flow i LAD.

### 12.2 Binance feeds

Subskrypcje:

- `{symbol}@aggTrade` — cross-venue taker flow,
- `{symbol}@depth` — cross-venue OBI/OFI sanity layer.

### 12.3 Funding & OI data

Źródło: Bybit REST API.

- Funding rate: poll `GET /v5/market/tickers` co 60 s, ekstrakcja `fundingRate` i `nextFundingTime`.
- Open Interest: poll `GET /v5/market/open-interest` co 60 s, interval `5min`.
- Funding z-score: rolling z-score na bazie ostatnich 168 pomiarów funding rate (= ~7 dni przy 8h funding intervals na Bybit).
- OI delta 5 min z-score: rolling z-score na bazie ostatnich 60 pomiarów OI delta 5 min (= 5h).

Funding/OI to context layer, nie trigger.

### 12.4 Canonical clock

- Raw event capture 1:1.
- Feature snapshot co 100 ms.
- Event processing venue-native (Bybit events processed by Bybit handler, Binance by Binance handler).
- Scoring na ostatnim zatwierdzonym snapshot.
- Execution może działać w krótszym horyzoncie, ale nie wolno używać feature’ów z niepełnego stanu (partial bucket).

### 12.5 WebSocket reconnect policy

Dla każdego połączenia WS:

|Parametr                  |Wartość         |
|--------------------------|----------------|
|Heartbeat interval        |20 s (ping)     |
|Max pong wait             |10 s            |
|Reconnect delay (initial) |1 s             |
|Reconnect delay (max)     |30 s            |
|Backoff multiplier        |2x (exponential)|
|Max consecutive reconnects|5 w ciągu 5 min |
|Jitter                    |random 0–500 ms |

Reguły:

- Podczas reconnect publicznego WS: buforowane eventy z innych WS nadal się przetwarzają, ale book danego venue = INVALID. Brak nowych wejść.
- Podczas reconnect private WS: natychmiastowy stop nowych wejść. Istniejące pozycje zachowują SL (server-side). Po reconnect: full position/order state reconciliation z REST przed wznowieniem.
- Po 5 nieudanych reconnectach w 5 min: KILL_SWITCH.
- Nigdy nie thrashować connect/disconnect. Minimalny interwał między kolejnymi próbami to wynik exponential backoff.

-----

## 13. Local book reconstruction

### 13.1 Binance runbook

1. Otwórz depth stream.
1. Buforuj eventy.
1. Pobierz REST snapshot.
1. Odrzuć eventy z `u < lastUpdateId`.
1. Pierwszy przetwarzany event musi spełniać `U <= lastUpdateId <= u`.
1. Każdy kolejny event musi mieć `pu == previous_u`.
1. Jeśli nie — pełny resync (back to step 1).
1. Wartości w eventach są absolutne.
1. `qty = 0` oznacza usunięcie poziomu.

### 13.2 Bybit runbook

1. Po subskrypcji przychodzi snapshot.
1. Budujesz local book.
1. Stosujesz delta.
1. `size = 0` oznacza usunięcie poziomu.
1. Nowy snapshot oznacza pełny reset local book.
1. Jeśli Bybit re-syła snapshot, uznajesz go za stan prawdziwy.

### 13.3 Book validity

Book = valid, gdy:

- `best_bid < best_ask`,
- `spread > 0`,
- poziomy są posortowane (bids descending, asks ascending),
- brak ujemnych qty,
- brak sequence gap (venue-specific validation),
- age ostatniego update’u < 5000 ms,
- snapshot seed wykonany poprawnie.

Jeśli book = invalid dłużej niż 3 s → pełny resync. Jeśli resync fails 3x → venue = DEGRADED.

-----

## 14. Context layer

### 14.1 Session model

System nie działa 24/7.

Handluje tylko w wybranych oknach:

- **EU_OPEN** — 08:00–12:00 UTC,
- **US_OVERLAP** — 14:00–20:00 UTC,
- opcjonalnie **FUNDING_ADJACENT** — 30 min przed i 15 min po funding settlement (wymaga potwierdzenia w replay/demo przed włączeniem).

Poza oknami: system zbiera dane i buduje context, ale nie generuje sygnałów.

### 14.2 Adaptive session monitoring

System monitoruje rolling 7-day volume distribution per hour per symbol. Jeśli > 30% volume danego symbolu wypada poza zdefiniowanymi oknami sesji, system generuje alert `SESSION_DRIFT` sugerujący reewaluację okien. Nie automatyczna zmiana — to jest alert do operatora.

### 14.3 Value framework

Każdy symbol ma stale liczone:

- rolling 24h composite VWAP,
- active session VWAP,
- active session volume profile (TPO-style),
- active session POC (Point of Control),
- value area high / low (70% volume rule),
- micro-profile 60 min (rolling),
- prior day high / low,
- prior day POC / VAH / VAL,
- local balance range (IQR of recent price distribution),
- prior failed auction extremes.

### 14.4 Regime engine

Dopuszczalne reżimy (mean reversion viable):

- **BALANCED** — price oscyluje wokół POC, narrow range, high rotation.
- **ROTATIONAL** — price rotuje między VAH/VAL, moderate range.
- **LOCAL_STRETCH** — price chwilowo rozciągnięta od value, ale brak trendu. MR viable z ciaśniejszym targetem.

Blokowane reżimy (mean reversion kontr-wskazane):

- **TREND_DAY** — one-directional, expanding range, value migrating.
- **VOL_EXPANSION** — realized vol >> baseline, chaotic flow.
- **INVALID** — brak wystarczających danych do klasyfikacji.

### 14.5 Regime classification rules

Regime jest klasyfikowany na podstawie:

|Feature                         |BALANCED   |ROTATIONAL     |LOCAL_STRETCH      |TREND_DAY            |VOL_EXPANSION|
|--------------------------------|-----------|---------------|-------------------|---------------------|-------------|
|`vol_short / vol_baseline`      |< 1.2      |0.8–1.5        |1.0–1.8            |> 1.5                |> 2.5        |
|Price vs value area             |Within VA  |Touches VAH/VAL|Outside VA, < 2 ATR|Outside VA, extending|Erratic      |
|Range expansion (vs session avg)|< 1.0x     |1.0–1.5x       |1.0–1.8x           |> 1.8x               |> 2.5x       |
|POC migration rate              |< 2 ticks/h|2–5 ticks/h    |< 5 ticks/h        |> 5 ticks/h          |Irrelevant   |

Klasyfikacja wymaga min 30 min danych w aktywnej sesji.

`regime_confidence` = weighted agreement across features. Trading enabled only when `regime_confidence >= 0.65`.

### 14.6 Regime filters

Filtry obowiązkowe:

- short-term realized vol vs baseline,
- spread stability (rolling CV of spread over 60 s),
- depth stability (rolling CV of top-10 depth over 60 s),
- book update rate,
- trade update rate,
- fair value distance,
- funding z-score,
- OI delta z-score,
- data quality composite.

### 14.7 Noise floor definition

`local_noise_floor` = median absolute tick-to-tick price change over the most recent 500 trades for the given symbol on the primary venue (Bybit). Wyrażone w tickach. Updated co 100 ms. Używane do:

- stop buffer calculation,
- sweep distance minimum,
- signal quality normalization.

### 14.8 Fair value anchor definition

`fair_value_anchor` = weighted average:

- 50% — active session VWAP,
- 30% — active session POC,
- 20% — micro-profile 60 min POC.

Jeśli sesja trwa < 30 min, fallback = 100% rolling 24h composite VWAP.

`fair_value_distance_bps` = `abs(current_mid - fair_value_anchor) / fair_value_anchor * 10000`.

-----

## 15. Feature schema

### 15.1 Order book features

- `bybit_obi_5bp` — OBI w bandwidth 5 bp od mid,
- `bybit_obi_10bp` — OBI w bandwidth 10 bp od mid,
- `binance_obi_5bp`, `binance_obi_10bp` — analogicznie,
- `queue_imbalance_top1` — `(bid_size_L1 - ask_size_L1) / (bid_size_L1 + ask_size_L1)`,
- `queue_imbalance_top3` — analogicznie dla top 3 levels,
- `bybit_microprice_offset_bps`, `binance_microprice_offset_bps`.

### 15.2 Flow features

- `cvd_1s`, `cvd_3s`, `cvd_10s` — cumulative volume delta w oknie,
- `bybit_ofi_top10_1s`, `binance_ofi_top10_1s` — order flow imbalance top 10 levels, 1 s window,
- `signed_notional_300ms`, `signed_notional_1s` — net signed taker notional,
- `trade_efficiency_score` — `abs(price_change_1s) / total_notional_1s` — price impact per unit notional. Niski = absorption. Wysoki = thin book / breakout.

### 15.3 LAD (Large Aggressor Delta)

Zastępuje „Smart Money Delta”.

Definicja large trade:

- `trade_notional >= rolling 97th percentile`,
- rolling window: ostatnie 20 000 trade events per symbol per venue.

Feature’y:

- `lad_buy_1s`, `lad_sell_1s` — notional sum of large trades per side, 1 s window,
- `lad_imbalance_1s` — `(lad_buy_1s - lad_sell_1s) / (lad_buy_1s + lad_sell_1s + epsilon)`,
- `lad_buy_count_3s`, `lad_sell_count_3s` — count of large trades per side, 3 s window.

### 15.4 Sweep / failure features

- `sweep_detected` — bool,
- `sweep_side` — `"buy"` | `"sell"` | `"none"`,
- `sweep_distance_ticks` — ile ticków penetracji poza mapped level,
- `sweep_distance_zscore` — z-score vs rolling distribution wick distance (500 recent wicks),
- `sweep_level_type` — typ levelu (patrz sekcja 16),
- `sweep_return_ratio` — `distance_returned / sweep_distance`. 1.0 = pełny powrót,
- `sweep_failure_time_ms` — czas od peak sweep extension do powrotu do/ponad level,
- `followthrough_failure_score` — 0–1, ile continuation price progress wypadło po sweep (0 = dużo = zły, 1 = zero = dobry),
- `reentry_into_range` — bool, czy cena wróciła do wnętrza value/range.

### 15.5 Confirmation features

- `absorption_score` — 0–1, ile notional zostało wchłonięte bez price progress,
- `exhaustion_score` — 0–1, spadek trade rate + notional po sweep,
- `replenishment_score` — 0–1, jak szybko depth po stronie support wraca po sweep,
- `level_hold_score` — 0–1, ile razy level został przetestowany bez trwałego przebicia,
- `iceberg_inference_score` — 0–1, prawdopodobieństwo ukrytej płynności na danym levelu,
- `spoof_probability` — 0–1, prawdopodobieństwo że visible depth jest spoof (rapid pull),
- `liquidation_burst_score` — 0–1, prawdopodobieństwo że sweep był napędzany cascading liquidations.

### 15.6 Market quality features

- `spread_ticks`,
- `spread_pctl` — percentyl spreadu w rolling session distribution,
- `spread_stability_score` — `1 - CV(spread, 60s)`, clamped to [0, 1],
- `depth_stability_score` — `1 - CV(top10_depth, 60s)`, clamped to [0, 1],
- `book_update_rate` — updates/sec,
- `trade_update_rate` — trades/sec,
- `data_quality_score` — composite: book validity, latency, freshness, sequence integrity,
- `latency_score` — `1 - min(median_latency_ms / 500, 1.0)`.

### 15.7 Fair value features

- `fair_value_distance_bps`,
- `target_distance_bps` — distance from entry to nearest TP,
- `session_vwap_distance_bps`,
- `session_poc_distance_bps`.

-----

## 16. Sweep detector — formalna definicja

### 16.1 Co jest sweep

Sweep = cenowe przebicie zmapowanego levelu, które spełnia:

1. **Level mapped**: istnieje wcześniej zidentyfikowany level z value framework (prior high/low, VAH, VAL, POC vicinity, LVN edge, failed auction extreme),
1. **Penetration**: cena przeszła poza level o >= `max(2 ticks, local_noise_floor)`,
1. **Volume condition**: łączny notional w strefie penetracji >= rolling 75th percentile 1 s notional,
1. **Return**: cena wróciła do/ponad level w `<= max_failure_ms` (default 3000 ms),
1. **No clean break**: w okresie penetracji brak sustained price progress (followthrough_failure_score >= 0.5).

### 16.2 Co nie jest sweep

- Wick < 2 ticks poza level = szum.
- Przebicie levelu z sustained continuation (> 3 s, nowe HH/LL bez powrotu) = breakout, nie sweep.
- Przebicie na niskim volume = gap/illiquidity event, nie sweep.

### 16.3 Sweep grading

`sweep_distance_zscore` mierzy jakość sweepout. Progi:

- zscore < 1.0 → too shallow, ignore.
- zscore 1.0–1.5 → marginal, wymaga silnego confirmation.
- zscore 1.5–2.5 → standard sweep.
- zscore > 2.5 → deep sweep, may be liquidation cascade (check `liquidation_burst_score`).

-----

## 17. Definicje setupów

### 17.1 Long setup

Long istnieje tylko, gdy:

1. Regime jest dopuszczalny (BALANCED, ROTATIONAL, LOCAL_STRETCH).
1. Cena dochodzi do zmapowanego dołkowego levelu.
1. Następuje sweep w dół (sekcja 16.1 spełniona, `sweep_side == "sell"`).
1. W 1–3 s cena wraca do wnętrza strefy / range / nad sweep level (`reentry_into_range == true`).
1. Po stronie sell pojawia się:
- absorption lub exhaustion (score >= 0.5),
- brak dalszego price progress (`followthrough_failure_score >= 0.5`),
- OFI flip up (Bybit OFI zmiana znaku na pozytywny),
- poprawa microprice / queue imbalance (microprice offset shifts bid-ward, queue imbalance top1 > 0).
1. Binance nie potwierdza dalszej continuation w dół (Binance CVD nie robi nowego low, Binance OFI nie utrzymuje negatywnego).
1. Execution conditions są poprawne (G6).
1. Target do fair value ma sens netto po kosztach (G7).

### 17.2 Short setup

Short jest lustrzanym odbiciem longa:

- sweep w górę (`sweep_side == "buy"`),
- powrót do wnętrza value/range,
- absorption/exhaustion po stronie buy,
- OFI flip down,
- brak Binance continuation support w górę,
- logiczny target do fair value w dół.

-----

## 18. Hard gates

Trade nie może powstać bez przejścia WSZYSTKICH hard gates.

### G1_REGIME_OK

`regime_name in {"BALANCED", "ROTATIONAL", "LOCAL_STRETCH"}`
AND `regime_confidence >= 0.65`

### G2_LEVEL_OK

Sweep wystąpił na ważnym poziomie:

- prior high/low,
- VAH/VAL,
- POC vicinity (± 3 ticks),
- LVN edge,
- failed auction extreme.

### G3_SWEEP_OK

Sweep nie jest szumem:

- `sweep_distance_ticks >= max(2, local_noise_floor)`,
- `sweep_distance_zscore >= 1.0`.

### G4_RETURN_OK

Powrót do range/value nastąpił w `<= max_failure_ms` (config, default 3000 ms).
`reentry_into_range == true`.

### G5_FLOW_CONFIRM_OK

`absorption_score >= 0.5` OR `exhaustion_score >= 0.5`,
AND `followthrough_failure_score >= 0.5`.

### G6_EXECUTION_OK

- `spread_pctl <= 80` (spread nie jest w top 20% swojej dystrybucji),
- book valid na obu venue,
- `data_quality_score >= 0.85`,
- `latency_score >= 0.80`,
- Bybit private WS alive.

### G7_TARGET_OK

- `target_distance_bps` po kosztach (maker fee + estimated slippage) `>= min_net_target_bps` (config, default 3.0 bps),
- stop geometry: `stop_distance_ticks >= 2` AND `RR_gross >= 1.2` (gross, before costs).

### G8_RISK_OK

- `cluster_exposure_r + intended_risk_r <= cluster_cap_r`,
- `risk_state` not in `{"PAUSED_SETUP", "PAUSED_STRATEGY", "KILL_SWITCH"}`,
- jeśli `risk_state == "REDUCED"` → only half-risk allowed.

-----

## 19. Scoring

Po hard gates liczymy `score_total` 0–100.

### 19.1 Component normalization

Każdy komponent jest normalizowany do zakresu 0–1 ZANIM zostanie pomnożony przez wagę.

Normalizacja per component:

|Component                  |Input feature(s)                                               |Normalization                                                                |
|---------------------------|---------------------------------------------------------------|-----------------------------------------------------------------------------|
|Sweep quality              |`sweep_distance_zscore`, `sweep_return_ratio`                  |`min(zscore / 3.0, 1.0) * sweep_return_ratio`                                |
|Return/failure quality     |`followthrough_failure_score`, `sweep_failure_time_ms`         |`followthrough_failure_score * (1 - min(failure_time / max_failure_ms, 1.0))`|
|Absorption/exhaustion      |`absorption_score`, `exhaustion_score`                         |`max(absorption, exhaustion)`                                                |
|OBI/OFI reversal quality   |OFI sign flip + OBI shift direction                            |`0–1 based on magnitude of flip relative to recent range`                    |
|LAD exhaustion/reversal    |`lad_imbalance_1s` sign alignment with setup                   |`abs(lad_imbalance) if aligned, 0 if opposing`                               |
|Fair value pull / target   |`target_distance_bps`, `fair_value_distance_bps`               |`min(target_distance / 10.0, 1.0)`                                           |
|Binance non-confirmation   |Binance CVD + OFI not confirming continuation                  |`0–1 based on degree of non-confirmation`                                    |
|Liquidation/trapped context|`liquidation_burst_score`                                      |Passed through (already 0–1)                                                 |
|Market quality             |`data_quality_score`, `latency_score`, `spread_stability_score`|`mean(dq, lat, spread_stab)`                                                 |

### 19.2 Wagi

|Component                        |Weight |
|---------------------------------|-------|
|Sweep quality                    |18     |
|Return/failure quality           |18     |
|Absorption/exhaustion            |16     |
|OBI/OFI reversal quality         |14     |
|LAD exhaustion/reversal          |8      |
|Fair value pull / target geometry|10     |
|Binance non-confirmation         |6      |
|Liquidation/trapped context      |4      |
|Market quality                   |6      |
|**Total**                        |**100**|

`score_total = sum(component_normalized * weight)`

### 19.3 Progi

- `score < 72` → NO_TRADE,
- `72 <= score < 80` → trade half-risk,
- `80 <= score < 88` → trade base-risk,
- `score >= 88` → trade max allowed risk.

### 19.4 Zasada nadrzędna

Score nie może obejść hard gates. Najpierw valid setup (all gates pass), potem jakość setupu (score).

-----

## 20. Execution policy

### 20.1 Ogólna zasada

Execution = maker-first, but not maker-only.

### 20.2 Signal age definition

`signal_age_ms` = `current_ts_ms - signal_decision.ts_ms`.

Wszystkie age-based checks odnoszą się do tego samego zegara. `aggressive_max_age_ms` to max `signal_age_ms` w momencie przejścia do SUBMIT_AGGRESSIVE. Nie jest to osobny timer od momentu aggressive submission.

### 20.3 Entry ladder

**PASSIVE_FIRST:**

Użyj Limit + PostOnly albo logicznego queue-join. Jeśli:

- spread akceptowalny,
- trigger świeży (`signal_age_ms < passive_ttl_ms`),
- reversal się utrzymuje,
- target geometry nie uciekł.

**TIMED_PASSIVE_RETRY:**

Jeśli brak fill po passive_ttl_ms:

- popraw cenę o 1 tick w kierunku mid,
- maksymalnie 1 retry,
- tylko jeśli setup nadal żyje (re-check hard gates G5, G6).

**AGGRESSIVE_CONFIRM:**

Jeśli reversal odjeżdża, ale sygnał wciąż żywy (`signal_age_ms < aggressive_max_age_ms`):

- mały entry agresywny (IOC lub controlowany taker-style fallback),
- size = half of intended size (risk reduction for taker cost).

Bybit dokumentuje, że market order jest realizowany jako IOC-limit przez engine, więc execution musi brać pod uwagę brak gwarancji fill przy zbyt agresywnym poślizgu.

**ABORT:**

Jeśli `signal_age_ms > max_signal_age_ms`:

- cancel pending entry,
- nie gonić rynku,
- transition to ABORTED.

### 20.4 Order lifecycle truth

Prawda o stanie ordera: private websocket, nie sam REST ack.

Bybit wyraźnie zaznacza, że ack z create-order jest tylko potwierdzeniem przyjęcia requestu i że status należy potwierdzać przez websocket.

-----

## 21. Execution state machine

### 21.1 Stany

- `IDLE`
- `WATCHING`
- `ARMED`
- `SUBMIT_PASSIVE`
- `WAIT_PASSIVE_ACK`
- `WAIT_PASSIVE_FILL`
- `PASSIVE_REPRICE`
- `SUBMIT_AGGRESSIVE`
- `WAIT_AGGRESSIVE_ACK`
- `WAIT_FILL`
- `POSITION_OPEN`
- `MANAGE_EXIT`
- `PARTIAL_EXIT`
- `CLOSE_POSITION`
- `ABORTED`
- `ERROR`

### 21.2 Przejścia

```
IDLE -> WATCHING                   # setup conditions emerging
WATCHING -> ARMED                  # sweep detected + return confirmed
WATCHING -> IDLE                   # setup conditions dissolved without trigger
ARMED -> SUBMIT_PASSIVE            # hard gates passed + score above threshold
ARMED -> SUBMIT_AGGRESSIVE         # passive skip (spread too tight, timing critical)
ARMED -> ABORTED                   # setup died before submission
SUBMIT_PASSIVE -> WAIT_PASSIVE_ACK
WAIT_PASSIVE_ACK -> WAIT_PASSIVE_FILL
WAIT_PASSIVE_ACK -> ERROR          # reject
WAIT_PASSIVE_FILL -> POSITION_OPEN # filled
WAIT_PASSIVE_FILL -> PASSIVE_REPRICE  # TTL expired, 1 retry allowed
PASSIVE_REPRICE -> WAIT_PASSIVE_FILL
WAIT_PASSIVE_FILL -> SUBMIT_AGGRESSIVE  # passive failed, aggressive fallback
WAIT_PASSIVE_FILL -> ABORTED      # signal stale, cancel
SUBMIT_AGGRESSIVE -> WAIT_AGGRESSIVE_ACK
WAIT_AGGRESSIVE_ACK -> WAIT_FILL
WAIT_AGGRESSIVE_ACK -> ERROR       # reject
WAIT_FILL -> POSITION_OPEN         # filled
WAIT_FILL -> ABORTED               # no fill (IOC expired)
POSITION_OPEN -> MANAGE_EXIT
MANAGE_EXIT -> PARTIAL_EXIT        # TP1 hit
MANAGE_EXIT -> CLOSE_POSITION      # SL or full TP
PARTIAL_EXIT -> MANAGE_EXIT        # continue managing remainder
CLOSE_POSITION -> IDLE
ANY -> ERROR                       # unhandled exception
ERROR -> IDLE                      # after error logging + cleanup
```

### 21.3 Abort conditions (pre-fill)

Abort w dowolnym stanie pre-fill, jeśli:

- `signal_age_ms > max_signal_age_ms`,
- OBI/OFI znowu odwróciły się przeciw setupowi (re-check G5),
- spread eksplodował (`spread_pctl > 95`),
- depth się zapadł (`depth_stability_score < 0.4`),
- private WS nie odpowiada,
- book invalid,
- Binance zaczął mocno wspierać continuation przeciw setupowi.

-----

## 22. Exit policy

### 22.1 Stop loss

Stop bazowy: poza ekstremum sweepu + micro-buffer.

Buffer = `max(2 ticks, local_noise_floor, short_ATR_fraction)`, where:

- `local_noise_floor` = median absolute tick-to-tick change, last 500 trades (sekcja 14.7),
- `short_ATR_fraction` = `ATR_1min * 0.3`.

Najwyższa z trzech wartości jest stosowana. Stop price jest zaokrąglany do tickSize (Decimal).

### 22.2 TP hierarchy

Dla longa:

1. TP1 = local mid / micro-VWAP (60 min),
1. TP2 = session VWAP,
1. TP3 = session POC lub opposite micro-balance edge.

Dla shorta odwrotnie.

Każdy TP musi spełniać: `distance_from_entry >= min_net_target_bps + estimated_costs_bps`. Jeśli TPn nie spełnia — zostaje usunięty, a jego alokacja przechodzi na TPn-1.

### 22.3 Time stop

Pozycja wychodzi natychmiast (market close), jeśli:

- nie wraca na fair value path w `max_hold_time_ms` (config, default 180 000 ms = 3 min),
- OFI znów odwraca się przeciw pozycji (utrzymuje adverse sign > 3 s),
- book pokazuje renewed continuation,
- adverse excursion > 60% stop distance bez szybkiej poprawy (< 2 s).

### 22.4 Partial exits

Default alokacja:

- TP1: 35%,
- TP2: 40%,
- TP3: reszta (25%).

Po TP1: stop na `max(BE, BE + round_trip_cost_bps)`, jeśli flow nadal wspiera pozycję. Jeśli flow neutralny lub adverse po TP1 — stop na BE immediately.

### 22.5 Session end handling

Jeśli sesja się kończy a pozycja jest otwarta:

- Jeśli PnL > 0: close at market.
- Jeśli PnL < 0 i < 50% of stop distance: close at market.
- Jeśli PnL < 0 i > 50% of stop distance: keep SL, ale nie otwieraj nowych pozycji.

-----

## 23. Risk framework

### 23.1 Correlated bucket

BTC/ETH/SOL traktujemy jako jeden skorelowany bucket.

`cluster_exposure_r` = suma risk R wszystkich otwartych pozycji w tym buckecie.

`cluster_cap_r` = 1.5 R (default). Oznacza to, że:

- max 1 pozycja at base risk (0.20%) + 1 at half risk (0.10%), lub
- max 1 pozycja at high score risk (0.30%) + 1 at half risk (0.10%), ale nie 2x base, itp.
- intent jest zablokowany jeśli `cluster_exposure_r + intended_risk_r > cluster_cap_r`.

### 23.2 Risk per trade

Startowe defaulty:

- base risk = 0.20% equity,
- high score risk = 0.30% equity,
- half-risk = 0.10% equity.

### 23.3 Leverage cap interaction

Max leverage = 5x.

Jeśli position size wymagany do pokrycia intended risk przy danym stop distance wymaga leverage > 5x:

- system OBNIŻA risk, NIE poszerza stopa,
- `effective_risk = equity * max_leverage * stop_distance / entry_price`,
- jeśli `effective_risk < half_risk` → trade jest skipped (zbyt ciasny stop dla tego instrumentu).

### 23.4 Risk modifiers

Risk obniżamy (floor = half-risk), gdy:

- `spread_pctl > 70`,
- `depth_stability_score < 0.65`,
- score ledwo przekracza próg (score 72–76: always half-risk),
- `data_quality_score < 0.90`,
- `cluster_exposure_r > 0.5 * cluster_cap_r`,
- volatility ratio (`vol_short / vol_baseline`) > 1.5.

### 23.5 Daily limits

- soft stop = -1.0% equity daily PnL,
- hard stop = -1.5% equity daily PnL.

Daily PnL reset: 00:00 UTC.

### 23.6 Consecutive loss rules

- 3 straty z rzędu w jednym setupie → wyłącz ten setup do końca dnia (PAUSED_SETUP).
- 2 porażki w warunkach trend-day mismatch (regime misclassified) → wyłącz cały MR engine do końca dnia (PAUSED_STRATEGY).
- 2 execution failures (rejects, timeout, desync) w < 5 min → przejdź w degraded mode.

### 23.7 Leverage

Cap: max 5x. Nie podlega override. Leverage jest obliczany jako `position_notional / equity`.

-----

## 24. Risk state machine

### 24.1 Stany

- `NORMAL` — full trading,
- `REDUCED` — half-risk only, no new aggressive entries,
- `PAUSED_SETUP` — specific setup disabled,
- `PAUSED_STRATEGY` — entire MR engine off, only exit management,
- `KILL_SWITCH` — all trading stopped, attempt to flatten.

### 24.2 Przejścia

```
NORMAL -> REDUCED
REDUCED -> NORMAL                  # conditions restored + cooldown elapsed
REDUCED -> PAUSED_SETUP
PAUSED_SETUP -> REDUCED            # next day or manual reset
REDUCED -> PAUSED_STRATEGY
PAUSED_STRATEGY -> NORMAL          # next day or manual reset
ANY -> KILL_SWITCH                 # irreversible within session
```

### 24.3 Triggery

**NORMAL → REDUCED:**

- soft daily drawdown hit,
- 2 losses in a row,
- `data_quality_score` drops below 0.80,
- volatility ratio > 2.0.

**REDUCED → NORMAL:**

- `data_quality_score` restored >= 0.85,
- volatility ratio < 1.5,
- AND cooldown >= 15 min since last trigger.

**REDUCED → PAUSED_SETUP:**

- 3 straty z rzędu w tym samym setupie,
- powtarzalne false positives (3+ signals with score > 72 but negative PnL),
- pogorszenie fill quality (avg slippage > 2x expected for 5+ trades).

**REDUCED → PAUSED_STRATEGY:**

- hard daily drawdown hit,
- private WS niestabilny (> 3 reconnects in 15 min),
- krytyczne problemy z feedem lub sync.

**ANY → KILL_SWITCH:**

- private WS dead (> 30 s no heartbeat),
- order lifecycle desync (WS state != expected state after reconciliation),
- 5 rejectów w 5 min,
- NTP clock drift > 2000 ms,
- Bybit system maintenance detected,
- manual stop (operator command).

-----

## 25. Degraded mode i failover policy

### 25.1 Stany jakości venue

- `FULLY_OPERATIONAL`,
- `BYBIT_PUBLIC_DEGRADED`,
- `BINANCE_DEGRADED`,
- `PRIVATE_WS_DEGRADED`,
- `BOOK_INVALID`,
- `METADATA_STALE`,
- `SYSTEM_ABNORMAL`.

### 25.2 Reguły

|Condition                        |Action                                                                               |
|---------------------------------|-------------------------------------------------------------------------------------|
|Binance padnie                   |Trading w REDUCED, only Bybit-primary triggers, Binance non-confirmation gate skipped|
|Bybit public book padnie         |Trading stop                                                                         |
|Private WS padnie                |Trading stop natychmiast                                                             |
|Instrument metadata stale (> 8h) |Zero nowych zleceń                                                                   |
|Book sync invalid                |Full resync, zero nowych wejść do odzyskania spójności                               |
|Bybit system maintenance < 15 min|SYSTEM_ABNORMAL, stop nowych wejść                                                   |

-----

## 26. Position sizing

### 26.1 Formula

```python
position_risk_usd = equity * risk_pct
stop_distance = abs(entry_price - stop_price)
qty_raw = position_risk_usd / stop_distance
qty_venue_valid = floor_to_qty_step(qty_raw, instrument.qtyStep)
```

### 26.2 Leverage check

```python
position_notional = qty_venue_valid * entry_price
required_leverage = position_notional / equity

if required_leverage > max_leverage:
    qty_venue_valid = floor_to_qty_step(equity * max_leverage / entry_price, instrument.qtyStep)
    effective_risk = qty_venue_valid * stop_distance
    if effective_risk < equity * half_risk_pct:
        # Trade skipped — stop too tight for this instrument at max leverage
        skip_trade()
```

### 26.3 Final clamps

Następnie clamp do:

- min order qty,
- max order qty (or max market qty for aggressive),
- leverage cap (sekcja 26.2),
- price band validity (`minPrice <= entry_price <= maxPrice`),
- cluster exposure cap.

Te ograniczenia muszą być zgodne z aktualnym metadata fetched z Bybit.

-----

## 27. Config defaults

```yaml
config_version: "2.0.0"

system:
  canonical_clock_ms: 100
  symbols: [BTCUSDT, ETHUSDT, SOLUSDT]
  execution_venue: bybit
  data_venues: [bybit, binance]
  ntp_max_offset_ms: 2000
  metadata_refresh_interval_h: 4
  metadata_stale_threshold_h: 8

sessions:
  enabled: true
  windows:
    - name: eu_open
      start_utc: "08:00"
      end_utc: "12:00"
      enabled: true
    - name: us_overlap
      start_utc: "14:00"
      end_utc: "20:00"
      enabled: true
    - name: funding_adjacent
      offset_before_min: 30
      offset_after_min: 15
      enabled: false
  session_drift_alert_pct: 30

regime:
  allow_balanced: true
  allow_rotational: true
  allow_local_stretch: true
  block_trend_day: true
  block_vol_expansion: true
  min_regime_confidence: 0.65
  min_session_data_minutes: 30

hard_gates:
  min_score: 72
  max_spread_pctl: 80
  min_sweep_distance_zscore: 1.0
  max_failure_ms: 3000
  min_absorption_or_exhaustion: 0.5
  min_followthrough_failure: 0.5
  min_depth_stability_score: 0.60
  min_data_quality_score: 0.85
  min_latency_score: 0.80
  max_signal_age_ms: 2000
  min_net_target_bps: 3.0
  min_gross_rr: 1.2

execution:
  passive_first: true
  passive_ttl_ms: 500
  passive_reprice_limit: 1
  passive_reprice_step_ticks: 1
  aggressive_fallback: true
  aggressive_max_signal_age_ms: 1200
  aggressive_size_fraction: 0.5
  cancel_on_stale_signal: true

risk:
  base_risk_pct: 0.20
  high_score_risk_pct: 0.30
  half_risk_pct: 0.10
  daily_soft_stop_pct: 1.0
  daily_hard_stop_pct: 1.5
  max_leverage: 5
  correlated_cluster_cap_r: 1.5
  min_viable_risk_pct: 0.10
  cooldown_after_reduced_min: 15

exit:
  tp1_pct: 35
  tp2_pct: 40
  tp3_pct: 25
  max_hold_time_ms: 180000
  adverse_excursion_close_pct: 60
  move_stop_to_be_after_tp1: true

websocket:
  heartbeat_interval_s: 20
  max_pong_wait_s: 10
  reconnect_delay_initial_s: 1
  reconnect_delay_max_s: 30
  reconnect_backoff_multiplier: 2
  max_reconnects_per_5min: 5
  reconnect_jitter_max_ms: 500

monitoring:
  venue_status_poll_interval_s: 60
  ntp_check_interval_s: 300
  health_log_interval_s: 10
```

-----

## 28. Logging

Każda próba trade’u ma logować:

- raw timestamps (exchange, recv, canonical),
- feature snapshot (full MicrostructureFeatures),
- regime snapshot,
- hard gates result (per-gate pass/fail),
- score components (per-component normalized + weighted),
- execution intent,
- order ack (REST response),
- websocket order status updates,
- fills (price, qty, fee),
- slippage (intended vs actual entry),
- cancel reason,
- exit reason,
- realized PnL (gross + net),
- risk state transition.

Typy logów:

- `raw_market_events` — parquet, append-only,
- `normalized_events` — parquet,
- `feature_snapshots` — parquet, per canonical tick,
- `signal_decisions` — JSON lines,
- `execution_actions` — JSON lines,
- `order_updates` — JSON lines,
- `position_updates` — JSON lines,
- `risk_transitions` — JSON lines,
- `health_events` — JSON lines,
- `config_snapshots` — YAML dump at boot + on change.

-----

## 29. Replay / backtest / demo validation

### 29.1 Minimalne wymagania

Replay i backtest muszą być:

- event-driven (same code path as live),
- local-book reconstructed (from raw events),
- fee-aware (maker/taker per venue, per tier),
- slippage-aware (queue position model for passive, spread model for aggressive),
- partial-fill aware,
- latency-aware (configurable simulated latency injection).

### 29.2 Acceptance criteria

Strategia może przejść dalej (z replay do demo, z demo do live) tylko, jeśli:

- net expectancy po kosztach > 0 over full test period,
- = 60% of rolling 2-week windows mają positive net PnL,
- demo directionally potwierdza replay (same signal directions, similar fill rates ± 20%),
- max drawdown <= daily hard stop (1.5%) in any single day,
- max drawdown <= 5% over full test period,
- fill quality: median slippage < 1.5 ticks for passive, < 3 ticks for aggressive.

-----

## 30. Graceful shutdown

### 30.1 Shutdown trigger

Shutdown może być wywołany przez:

- operator command (SIGTERM / SIGINT / manual),
- KILL_SWITCH activation,
- unrecoverable error.

### 30.2 Shutdown sequence

1. Stop signal engine — no new signals.
1. Cancel all pending orders (REST cancel + WS confirmation).
1. Wait up to 5 s for cancel confirmations.
1. If open positions exist:
- If KILL_SWITCH: market close all immediately.
- If graceful: keep SL active (server-side), log position state, exit.
1. Close all WS connections.
1. Flush all log buffers to disk.
1. Write final state snapshot (positions, PnL, risk state).
1. Exit.

-----

## 31. Deployment roadmap

**Faza 1 — Infrastructure:**

- boot, instrument metadata, NTP sync,
- public feeds (Bybit + Binance),
- private WS,
- raw logging,
- local books,
- WS reconnect handler,
- graceful shutdown.

**Faza 2 — Context:**

- value engine (VWAP, profile, level map),
- session model,
- regime engine,
- noise floor calculation.

**Faza 3 — Features:**

- OBI / OFI / microprice,
- CVD / LAD,
- sweep detector (formal definition),
- absorption / exhaustion / replenishment,
- trade efficiency, signed notional,
- feature snapshot assembly.

**Faza 4 — Signals:**

- hard gates (all 8),
- score normalizer,
- scorer,
- long/short setups.

**Faza 5 — Execution:**

- order validator (metadata-aware),
- execution FSM,
- stale signal guard,
- SL/TP manager,
- partial exit logic.

**Faza 6 — Risk:**

- position sizer (with leverage cap interaction),
- risk FSM,
- degraded mode,
- kill switch,
- cluster exposure,
- daily limits.

**Faza 7 — Replay & Validation:**

- event replay engine,
- fill simulator,
- walk-forward,
- acceptance criteria validation.

**Faza 8 — Demo forward:**

- najpierw BTC (2+ tygodnie),
- potem ETH (2+ tygodnie),
- potem SOL (2+ tygodnie),
- potem all three concurrent (2+ tygodnie),
- acceptance criteria must pass at each stage.

-----

## 32. Reguły końcowe

**Reguła 1:** Nie handluj order flow bez zmapowanego miejsca i logicznego targetu do value.

**Reguła 2:** Nie handluj failed sweepu bez potwierdzenia, że continuation naprawdę umarło.

**Reguła 3:** Nie handluj dobrego sygnału w złym execution state.

**Reguła 4:** Private WS jest źródłem prawdy o orderach.

**Reguła 5:** Book desync = brak trade’ów.

**Reguła 6:** Brak metadata = brak trade’ów.

**Reguła 7:** Bybit degraded lub private WS degraded = natychmiastowy stop nowych wejść.

**Reguła 8:** Najpierw stabilność, potem agresja.

**Reguła 9:** Leverage cap ogranicza size, nigdy nie poszerza stopa.

**Reguła 10:** Float nie dotyka execution logic. Decimal only dla cen i qty w order path.

**Reguła 11:** Każdy config musi mieć version. Każdy boot loguje config snapshot.

**Reguła 12:** Graceful shutdown > hard kill. Zawsze flush logs, zawsze confirm cancel.