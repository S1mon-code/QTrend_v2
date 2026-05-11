"""Shared type aliases and small value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd  # pd.Timestamp is used in Leg/Fill field annotations below


class ActionKind(str, Enum):
    HOLD = "HOLD"
    BUY = "BUY"
    SELL = "SELL"
    FLAT_ALL = "FLAT_ALL"


@dataclass(frozen=True)
class Action:
    """Atomic instruction from StateMachine to ExecutionAdapter."""

    kind: ActionKind
    lots: int  # absolute lot count for BUY/SELL; 0 for HOLD/FLAT_ALL
    reason: str

    def __post_init__(self) -> None:
        if self.kind in (ActionKind.BUY, ActionKind.SELL) and self.lots <= 0:
            raise ValueError(f"{self.kind.value} requires lots > 0, got {self.lots}")
        if self.kind in (ActionKind.HOLD, ActionKind.FLAT_ALL) and self.lots != 0:
            raise ValueError(f"{self.kind.value} requires lots == 0, got {self.lots}")


@dataclass(frozen=True)
class Leg:
    """A single entry transaction in the current open round."""

    timestamp: pd.Timestamp
    price: float
    lots: int


@dataclass(frozen=True)
class Fill:
    """Reported by ExecutionAdapter after acting on an Action."""

    timestamp: pd.Timestamp
    kind: ActionKind
    lots: int
    price: float
    reason: str
