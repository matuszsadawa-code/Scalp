# VOLF HYPER APEX 2026

Repo bootstrap for Phase 0-1 foundation of intraday mean-reversion engine.

## Current scope

- Layered directory skeleton (`core -> ... -> risk`).
- Strictly typed core domain models and `Result` pattern.
- Immutable config models and YAML loader.
- Runtime/config startup validation entrypoint (`app.py`).
- Infrastructure primitives:
  - canonical clock bucket helpers,
  - local orderbook state with snapshot/delta logic and invalidation,
  - Binance depth sequence validation (`pu == previous_u`) with resync trigger,
  - websocket reconnect backoff + jitter policy,
  - degraded mode decision policy,
  - graceful shutdown coordinator.
- Unit tests for config loader, book logic, sequence checks, reconnect policy, and degraded mode.

## Run

```bash
python app.py
pytest
mypy core config boot marketdata risk shutdown app.py
```
