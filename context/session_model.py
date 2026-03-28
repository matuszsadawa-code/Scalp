from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone


@dataclass(frozen=True, slots=True)
class SessionWindow:
    name: str
    start_utc: time
    end_utc: time


@dataclass(frozen=True, slots=True)
class SessionModel:
    windows: tuple[SessionWindow, ...]

    def is_active(self, ts_ms: int) -> bool:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        now_t = dt.time()
        return any(window.start_utc <= now_t < window.end_utc for window in self.windows)


def default_session_model() -> SessionModel:
    return SessionModel(
        windows=(
            SessionWindow(name="eu_open", start_utc=time(8, 0), end_utc=time(12, 0)),
            SessionWindow(name="us_overlap", start_utc=time(14, 0), end_utc=time(20, 0)),
        )
    )
