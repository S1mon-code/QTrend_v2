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


def _make_daily_peak_then_crash(n_up: int = 60, n_dn: int = 5) -> pd.DataFrame:
    """Daily series that rises to a peak, then sharply reverses — designed to
    trigger the StateMachine's ATR trailing stop inside the bias window."""
    idx = pd.date_range("2024-01-01", periods=n_up + n_dn, freq="B")
    close_up = [3000 + i * 5 for i in range(n_up)]
    peak = close_up[-1]
    # Sharp crash: down ~3% per day for n_dn days.
    close_dn = [peak * (1 - 0.03 * (i + 1)) for i in range(n_dn)]
    close = close_up + close_dn
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


def test_run_window_trailing_stop_credits_cash():
    """A sharp crash after an uptrend must trigger ATR trailing stop, which
    must execute a SELL through the simulator and credit cash. The earlier
    backtest implementation silently dropped lots when stop fired, leaving
    cash with a large negative balance and equity stuck at -lots × buy_price."""
    daily = _make_daily_peak_then_crash(n_up=60, n_dn=5)
    h1 = _make_h1_from_daily(daily)
    window = BiasWindow(start=daily.index[0], end=daily.index[-1], note="crash test")
    result = run_window(
        window=window,
        daily=daily,
        h1=h1,
        forecast=EWMAC(),
        sizer=Sizer(),
        pullback=ConnorsPullback(),
        state_machine=StateMachine(atr_multiplier=3.0),
        simulator=SimulatorAdapter(bars=h1, tx_cost_per_lot=0.0),
    )
    # The crash MUST produce at least one FLAT_ALL row in the action log
    # (either from trailing stop during the crash or from end-of-window flat).
    assert "FLAT_ALL" in result.actions_log["kind"].values
    flat_rows = result.actions_log[result.actions_log["kind"] == "FLAT_ALL"]
    # Every FLAT_ALL must have lots > 0 (proves we actually closed a real
    # position rather than silently dropping it).
    assert (flat_rows["lots"] > 0).all()
    # Final equity should be bounded by realistic loss: capped roughly at
    # -(max_lots × crash_depth × buy_price). With max 5 lots × ~15% crash on
    # 3300 price, max loss ≈ 2500. We assert > -3000 (no silent leg-drop disaster).
    assert result.equity.iloc[-1] > -3000
