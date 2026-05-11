"""End-to-end smoke: real HC data + template bias_windows.csv → both reports."""

from __future__ import annotations

from pathlib import Path

import pytest

from qtrend_v2 import Strategy
from qtrend_v2.bias import BiasWindowLoader
from qtrend_v2.data import load_hc_1h, load_hc_daily
from qtrend_v2.report import render_aggregate_report, render_window_report

DAILY_PATH = Path("/Users/simon/Desktop/data/CN/market/continuous/.cache/HC_daily.parquet")
BIAS_PATH = Path(__file__).parent.parent / "data" / "bias_windows.csv"


@pytest.mark.skipif(not DAILY_PATH.exists(), reason="HC data not present")
def test_smoke_end_to_end(tmp_path):
    daily = load_hc_daily()
    h1 = load_hc_1h()
    loader = BiasWindowLoader(BIAS_PATH)
    strat = Strategy()
    results = []
    for window in loader.windows():
        if window.start < daily.index.min() or window.end > daily.index.max():
            continue
        result = strat.run_window(window=window, daily=daily, h1=h1)
        out = tmp_path / f"window_{window.start.date()}.html"
        render_window_report(result=result, daily=daily, output_path=out)
        results.append(result)
        assert out.exists()
    assert results, "no windows in range — extend or fix bias_windows.csv"
    agg_out = tmp_path / "aggregate.html"
    render_aggregate_report(results=results, output_path=agg_out)
    assert agg_out.exists()
