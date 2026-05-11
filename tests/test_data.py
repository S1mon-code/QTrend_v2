"""Tests for HC bar loaders."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qtrend_v2.data import load_hc_1h, load_hc_daily

DATA_ROOT = Path("/Users/simon/Desktop/data/CN/market/continuous/.cache")
DAILY_PATH = DATA_ROOT / "HC_daily.parquet"
H1_PATH = DATA_ROOT / "HC_60min.parquet"


@pytest.mark.skipif(not DAILY_PATH.exists(), reason="HC daily parquet not present")
def test_load_hc_daily_has_ohlcv_and_datetime_index():
    df = load_hc_daily()
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing
    for col in ("open", "high", "low", "close", "volume"):
        assert col in df.columns, f"missing {col}"
    assert (df["close"] > 0).all()


@pytest.mark.skipif(not H1_PATH.exists(), reason="HC 1H parquet not present")
def test_load_hc_1h_has_ohlcv_and_datetime_index():
    df = load_hc_1h()
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing
    for col in ("open", "high", "low", "close", "volume"):
        assert col in df.columns


@pytest.mark.skipif(not DAILY_PATH.exists(), reason="HC daily parquet not present")
def test_load_hc_daily_date_range_filter():
    df = load_hc_daily(start="2023-01-01", end="2023-12-31")
    assert df.index.min() >= pd.Timestamp("2023-01-01")
    assert df.index.max() <= pd.Timestamp("2023-12-31")
