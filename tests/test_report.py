"""Tests for HTML report generation."""

from __future__ import annotations

import pandas as pd

from qtrend_v2 import Strategy
from qtrend_v2.bias import BiasWindow
from qtrend_v2.report import render_window_report


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


def test_render_window_report_writes_html(tmp_path):
    daily = _daily(60)
    h1 = _h1(daily)
    window = BiasWindow(start=daily.index[0], end=daily.index[-1], note="t1")
    result = Strategy().run_window(window=window, daily=daily, h1=h1)
    out = tmp_path / "window.html"
    render_window_report(result=result, daily=daily, output_path=out)
    assert out.exists()
    html = out.read_text()
    assert "QTrend_v2" in html
    assert "t1" in html
