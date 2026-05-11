"""Plug-in interface for trend-strength forecast signals."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class ForecastSignal(ABC):
    """Long-only forecast in [0, +20].

    Implementations consume daily OHLCV bars and emit a per-bar forecast Series
    aligned to the daily index. Negative-trend signals are clipped to 0; the
    engine never goes short.
    """

    @abstractmethod
    def compute(self, daily_bars: pd.DataFrame) -> pd.Series:
        """Return forecast Series indexed by daily timestamp, values in [0, 20]."""
