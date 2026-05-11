"""Tests for EWMAC(16, 64) forecast signal."""

from __future__ import annotations

import numpy as np
import pandas as pd

from qtrend_v2.forecast.ewmac import EWMAC


def _make_bars(close_series: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(close_series), freq="B")
    return pd.DataFrame(
        {
            "open": close_series,
            "high": close_series,
            "low": close_series,
            "close": close_series,
            "volume": 1000,
        },
        index=idx,
    )


def test_ewmac_output_shape_and_bounds():
    close = list(np.linspace(3000, 3600, 250))
    bars = _make_bars(close)
    forecast = EWMAC().compute(bars)
    assert isinstance(forecast, pd.Series)
    assert len(forecast) == len(bars)
    assert (forecast >= 0).all()
    assert (forecast <= 20).all()


def test_ewmac_positive_on_uptrend():
    close = list(np.linspace(3000, 3600, 250))
    bars = _make_bars(close)
    forecast = EWMAC().compute(bars)
    assert forecast.iloc[-1] > 5


def test_ewmac_zero_on_downtrend_long_only():
    close = list(np.linspace(3600, 3000, 250))
    bars = _make_bars(close)
    forecast = EWMAC().compute(bars)
    assert forecast.iloc[-1] == 0.0


def test_ewmac_warmup_returns_zero_or_nan_safe():
    close = list(np.linspace(3000, 3050, 5))
    bars = _make_bars(close)
    forecast = EWMAC().compute(bars)
    assert np.isfinite(forecast.values).all()
    assert (forecast >= 0).all() and (forecast <= 20).all()
