"""Top-level Strategy class test."""

from __future__ import annotations

import pandas as pd

from qtrend_v2 import Strategy
from qtrend_v2.bias import BiasWindow


def _daily_uptrend(n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = [3000 + i * 5 for i in range(n)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 5 for c in close],
            "low": [c - 5 for c in close],
            "close": close,
            "volume": 1000,
        },
        index=idx,
    )


def _h1_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ts, row in daily.iterrows():
        for h in range(4):
            ts_h = ts.replace(hour=9 + h * 2)
            close = row["close"] + (h - 1.5) * 0.1
            rows.append(
                {
                    "datetime": ts_h,
                    "open": close,
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "volume": 100,
                }
            )
    return pd.DataFrame(rows).set_index("datetime")


def test_strategy_run_window_smoke():
    daily = _daily_uptrend(60)
    h1 = _h1_from_daily(daily)
    window = BiasWindow(start=daily.index[0], end=daily.index[-1], note="t")
    strat = Strategy()
    result = strat.run_window(window=window, daily=daily, h1=h1)
    assert result.window == window
    assert len(result.lot_history) > 0
