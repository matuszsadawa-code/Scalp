# VOLF HYPER APEX 2026

Repo bootstrap for Phase 0 (scaffolding) of intraday mean-reversion engine.

## Current scope

- Layered directory skeleton (`core -> ... -> risk`).
- Strictly typed core domain models and Result pattern.
- Immutable config models and YAML loader.
- Startup runtime/config validation entrypoint (`app.py`).
- Initial unit test for config loading.

## Run

```bash
python app.py
pytest
```
