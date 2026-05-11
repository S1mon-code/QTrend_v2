"""EWMAC trend-strength forecast (Carver style, long-only clipped)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from qtrend_v2.forecast.base import ForecastSignal


class EWMAC(ForecastSignal):
    """EWMAC(fast, slow) — exponentially-weighted moving-average crossover.

    Following Carver (Systematic Trading), the raw forecast is

        raw = EMA(close, fast) - EMA(close, slow)

    normalised by an exponentially-weighted estimate of price volatility, then
    scaled to a long-run absolute value of ~10 and capped at ±20. Long-only:
    negative values clipped to 0.

    Defaults: fast=16, slow=64 (Carver's medium-term span).
    """

    def __init__(self, fast: int = 16, slow: int = 64, scalar: float = 4.1, cap: float = 20.0):
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be < slow ({slow})")
        self.fast = fast
        self.slow = slow
        self.scalar = scalar
        self.cap = cap

    def compute(self, daily_bars: pd.DataFrame) -> pd.Series:
        close = daily_bars["close"].astype(float)
        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()
        raw = ema_fast - ema_slow

        price_change = close.diff().abs()
        vol = price_change.ewm(span=25, adjust=False).mean().replace(0, np.nan)

        scaled = (raw / vol) * self.scalar
        scaled = scaled.clip(lower=0.0, upper=self.cap)
        scaled = scaled.fillna(0.0)
        return scaled
