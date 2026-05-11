"""Shared pytest fixtures for qtrend_v2 tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_daily() -> pd.DataFrame:
    """120 daily bars: 60 trending up, 60 sideways. RangeIndex; datetime col."""
    rng = pd.date_range("2024-01-01", periods=120, freq="B")
    trend = np.linspace(3000, 3600, 60)
    flat = np.full(60, 3600.0) + np.random.default_rng(42).normal(0, 10, 60)
    close = np.concatenate([trend, flat])
    df = pd.DataFrame(
        {
            "datetime": rng,
            "open": close * 0.999,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": 1000,
        }
    )
    return df


@pytest.fixture
def synthetic_h1(synthetic_daily: pd.DataFrame) -> pd.DataFrame:
    """4 1H bars per daily bar, derived from synthetic_daily close."""
    rows = []
    for _, day in synthetic_daily.iterrows():
        for hour_offset in (9, 10, 11, 13):
            ts = day["datetime"].replace(hour=hour_offset, minute=1)
            rows.append(
                {
                    "datetime": ts,
                    "open": day["close"] * 0.999,
                    "high": day["close"] * 1.002,
                    "low": day["close"] * 0.998,
                    "close": day["close"],
                    "volume": 250,
                }
            )
    return pd.DataFrame(rows)
