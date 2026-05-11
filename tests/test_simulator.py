"""Tests for SimulatorAdapter."""

from __future__ import annotations

import pandas as pd

from qtrend_v2.execution.simulator import SimulatorAdapter
from qtrend_v2.types import Action, ActionKind


def test_buy_fill_at_next_1h_open():
    bars = pd.DataFrame(
        {
            "open": [3500.0, 3510.0, 3520.0],
            "high": [3505, 3515, 3525],
            "low": [3495, 3505, 3515],
            "close": [3503, 3513, 3523],
        },
        index=pd.date_range("2024-01-02 10:00", periods=3, freq="h"),
    )
    sim = SimulatorAdapter(bars=bars, tx_cost_per_lot=1.0)
    fill = sim.execute(
        action=Action(kind=ActionKind.BUY, lots=2, reason="enter"),
        current_ts=bars.index[0],
    )
    assert fill is not None
    assert fill.kind == ActionKind.BUY
    assert fill.lots == 2
    assert fill.price == 3510.0 + 1.0
    assert fill.timestamp == bars.index[1]


def test_sell_fill_at_next_1h_open_minus_cost():
    bars = pd.DataFrame(
        {
            "open": [3500.0, 3510.0, 3520.0],
            "high": [3505, 3515, 3525],
            "low": [3495, 3505, 3515],
            "close": [3503, 3513, 3523],
        },
        index=pd.date_range("2024-01-02 10:00", periods=3, freq="h"),
    )
    sim = SimulatorAdapter(bars=bars, tx_cost_per_lot=1.0)
    fill = sim.execute(
        action=Action(kind=ActionKind.SELL, lots=1, reason="scale_down"),
        current_ts=bars.index[0],
    )
    assert fill is not None
    assert fill.price == 3510.0 - 1.0


def test_hold_returns_none():
    bars = pd.DataFrame(
        {"open": [3500.0], "high": [3505], "low": [3495], "close": [3503]},
        index=pd.date_range("2024-01-02 10:00", periods=1, freq="h"),
    )
    sim = SimulatorAdapter(bars=bars)
    fill = sim.execute(
        action=Action(kind=ActionKind.HOLD, lots=0, reason="at_target"),
        current_ts=bars.index[0],
    )
    assert fill is None


def test_no_next_bar_returns_none():
    bars = pd.DataFrame(
        {"open": [3500.0], "high": [3505], "low": [3495], "close": [3503]},
        index=pd.date_range("2024-01-02 10:00", periods=1, freq="h"),
    )
    sim = SimulatorAdapter(bars=bars)
    fill = sim.execute(
        action=Action(kind=ActionKind.BUY, lots=1, reason="enter"),
        current_ts=bars.index[0],
    )
    assert fill is None
