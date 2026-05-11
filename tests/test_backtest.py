"""Unit-level test: backtest driver runs over a synthetic window."""

from __future__ import annotations

import pandas as pd

from qtrend_v2.backtest import WindowResult, run_window
from qtrend_v2.bias import BiasWindow
from qtrend_v2.execution.simulator import SimulatorAdapter
from qtrend_v2.forecast.ewmac import EWMAC
from qtrend_v2.pullback.connors import ConnorsPullback
from qtrend_v2.sizing import Sizer
from qtrend_v2.state_machine import StateMachine


def _make_daily_uptrend(n: int = 60) -> pd.DataFrame:
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


def _make_h1_from_daily(daily: pd.DataFrame, bars_per_day: int = 4) -> pd.DataFrame:
    rows = []
    for ts, row in daily.iterrows():
        for h in range(bars_per_day):
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


def test_run_window_returns_result_with_pnl_and_log():
    daily = _make_daily_uptrend(60)
    h1 = _make_h1_from_daily(daily)
    window = BiasWindow(start=daily.index[0], end=daily.index[-1], note="test")
    result = run_window(
        window=window,
        daily=daily,
        h1=h1,
        forecast=EWMAC(),
        sizer=Sizer(),
        pullback=ConnorsPullback(),
        state_machine=StateMachine(),
        simulator=SimulatorAdapter(bars=h1),
    )
    assert isinstance(result, WindowResult)
    assert result.window == window
    assert isinstance(result.equity, pd.Series)
    assert isinstance(result.actions_log, pd.DataFrame)
    assert result.equity.iloc[-1] >= result.equity.iloc[0]
