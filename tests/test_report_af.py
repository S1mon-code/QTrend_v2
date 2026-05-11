"""Tests for the AlphaForge report adapter."""

from __future__ import annotations

import importlib

import pandas as pd
import pytest

from qtrend_v2 import Strategy
from qtrend_v2.bias import BiasWindow

_AF_AVAILABLE = importlib.util.find_spec("alphaforge") is not None
skipif_no_af = pytest.mark.skipif(not _AF_AVAILABLE, reason="alphaforge not installed")


def _daily(n: int = 60) -> pd.DataFrame:
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


def _h1(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ts, row in daily.iterrows():
        for h in range(4):
            ts_h = ts.replace(hour=9 + h * 2)
            close = row["close"]
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


@skipif_no_af
def test_to_backtest_result_returns_backtestresult():
    from alphaforge.engine.result import BacktestResult

    from qtrend_v2.report_af import InstrumentSpec, to_backtest_result

    daily = _daily(60)
    h1 = _h1(daily)
    window = BiasWindow(start=daily.index[0], end=daily.index[-1], note="test")
    wr = Strategy().run_window(window=window, daily=daily, h1=h1)

    af = to_backtest_result(wr, initial_capital=1_000_000, spec=InstrumentSpec.hc())
    assert isinstance(af, BacktestResult)
    assert af.strategy_name.startswith("QTrend_v2")
    assert af.equity_curve.iloc[0] == pytest.approx(1_000_000, abs=1e-6)
    assert isinstance(af.daily_returns, pd.Series)
    assert len(af.equity_curve) == len(af.daily_returns)
    assert af.metadata["instrument"] == "HC"
    assert af.metadata["multiplier"] == 10.0


@skipif_no_af
def test_to_backtest_result_handles_empty_window():
    from qtrend_v2.backtest import WindowResult
    from qtrend_v2.report_af import to_backtest_result

    empty = WindowResult(
        window=BiasWindow(
            start=pd.Timestamp("2024-01-01"), end=pd.Timestamp("2024-01-02"), note="empty"
        ),
        equity=pd.Series(dtype=float),
        actions_log=pd.DataFrame(columns=["ts", "kind", "lots", "price", "reason", "current_lots"]),
        lot_history=pd.Series(dtype=int),
        forecast_history=pd.Series(dtype=float),
    )
    af = to_backtest_result(empty, initial_capital=1_000_000)
    assert af.equity_curve.iloc[0] == 1_000_000


@skipif_no_af
def test_trades_df_has_raw_fill_schema():
    from qtrend_v2.report_af import to_backtest_result

    daily = _daily(60)
    h1 = _h1(daily)
    window = BiasWindow(start=daily.index[0], end=daily.index[-1], note="t")
    wr = Strategy().run_window(window=window, daily=daily, h1=h1)
    af = to_backtest_result(wr)
    if af.trades is not None and len(af.trades) > 0:
        required_cols = {
            "datetime",
            "symbol",
            "side",
            "lots",
            "price",
            "commission",
            "slippage_cost",
            "trading_day",
            "is_close_today",
        }
        assert required_cols.issubset(set(af.trades.columns))
        # Side encoded as int ±1.
        assert af.trades["side"].isin([1, -1]).all()
        # Commission must be positive whenever there is a fill.
        assert (af.trades["commission"] >= 0).all()


@skipif_no_af
def test_render_alphaforge_report_writes_html(tmp_path):
    from qtrend_v2.report_af import render_alphaforge_report

    daily = _daily(60)
    h1 = _h1(daily)
    window = BiasWindow(start=daily.index[0], end=daily.index[-1], note="t1")
    wr = Strategy().run_window(window=window, daily=daily, h1=h1)
    out = tmp_path / "af.html"
    render_alphaforge_report(window_result=wr, output_path=out)
    assert out.exists()
    html = out.read_text()
    # AlphaForge reports include specific marker classes/divs.
    assert "QTrend_v2" in html
    # At least the equity chart marker should appear.
    assert "equity" in html.lower()
