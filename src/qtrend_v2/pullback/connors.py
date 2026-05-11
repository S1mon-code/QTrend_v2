"""Connors-style stateful pullback modulator on 1H bars.

State machine:
    offset ∈ {-1, 0}, starts at 0.
    RSI(2) > overbought  and offset == 0  → offset := -1   (trim)
    RSI(2) < oversold    and offset == -1 → offset := 0    (reload undoes trim)
Gated: inactive (no transitions) when current_forecast < forecast_min.
Output: clip(current_target + offset, 0, current_target).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(close: pd.Series, period: int) -> pd.Series:
    """Wilder-style RSI(period). Returns 50 during warm-up (neutral).

    When roll_dn = 0 and roll_up > 0 (pure up-streak), RS = +inf and RSI = 100.
    When both are 0 (no movement), the formula yields NaN which is filled to 50.
    Do NOT pre-replace zeros with NaN — that suppresses the legitimate RSI=100
    case and silently breaks trim triggers on monotonic uptrends.
    """
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    roll_dn = down.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = roll_up / roll_dn
        rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


class ConnorsPullback:
    def __init__(
        self,
        rsi_period: int = 2,
        overbought: float = 95.0,
        oversold: float = 10.0,
        forecast_min: float = 8.0,
    ):
        self.rsi_period = rsi_period
        self.overbought = overbought
        self.oversold = oversold
        self.forecast_min = forecast_min
        self._offset: int = 0

    def reset(self) -> None:
        self._offset = 0

    def adjust(
        self,
        h1_bars: pd.DataFrame,
        current_forecast: float,
        current_target: int,
    ) -> int:
        """Return the modulated target ∈ [0, current_target]."""
        if current_target <= 0:
            return 0

        if current_forecast < self.forecast_min:
            return max(0, min(current_target + self._offset, current_target))

        if len(h1_bars) < self.rsi_period + 1:
            return current_target

        rsi = _rsi(h1_bars["close"], self.rsi_period).iloc[-1]

        if self._offset == 0 and rsi > self.overbought:
            self._offset = -1
        elif self._offset == -1 and rsi < self.oversold:
            self._offset = 0

        return max(0, min(current_target + self._offset, current_target))
