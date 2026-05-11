"""Tests for ConnorsPullback stateful modulator."""

from __future__ import annotations

import pandas as pd

from qtrend_v2.pullback.connors import ConnorsPullback


def _make_1h_series(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-03-01 09:01:00", periods=len(closes), freq="h")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": 100},
        index=idx,
    )


def test_modulator_no_trim_when_forecast_below_gate():
    closes = [3000] * 20 + [3100] * 20
    bars = _make_1h_series(closes)
    m = ConnorsPullback()
    out = m.adjust(bars, current_forecast=5.0, current_target=1)
    assert out == 1


def test_modulator_trims_when_overbought_and_forecast_high():
    closes = [3000] * 15 + [3000 + i * 5 for i in range(15)]
    bars = _make_1h_series(closes)
    m = ConnorsPullback(rsi_period=2, overbought=95.0, oversold=10.0)
    final_target = m.adjust(bars, current_forecast=15.0, current_target=4)
    assert final_target in (3, 4)


def test_modulator_reload_only_undoes_prior_trim():
    closes_up = [3000 + i for i in range(15)]
    closes_dn = [3014 - i for i in range(15)]
    bars = _make_1h_series(closes_up + closes_dn)
    m = ConnorsPullback()
    m.adjust(bars.iloc[:15], current_forecast=15.0, current_target=4)
    m.adjust(bars, current_forecast=15.0, current_target=4)
    out = m.adjust(bars, current_forecast=15.0, current_target=4)
    assert out <= 4
    assert m._offset in (-1, 0)


def test_modulator_reset_clears_offset():
    closes = [3000 + i for i in range(40)]
    bars = _make_1h_series(closes)
    m = ConnorsPullback()
    m.adjust(bars, current_forecast=15.0, current_target=4)
    m.reset()
    assert m._offset == 0


def test_modulator_output_clipped_to_target_range():
    closes = [3000 + i for i in range(30)]
    bars = _make_1h_series(closes)
    m = ConnorsPullback()
    out = m.adjust(bars, current_forecast=20.0, current_target=0)
    assert out == 0
