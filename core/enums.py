from __future__ import annotations

from enum import StrEnum


class Venue(StrEnum):
    BYBIT = "bybit"
    BINANCE = "binance"


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class TakerSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"


class RiskState(StrEnum):
    NORMAL = "normal"
    REDUCED = "reduced"
    PAUSED_SETUP = "paused_setup"
    PAUSED_STRATEGY = "paused_strategy"
    KILL_SWITCH = "kill_switch"
