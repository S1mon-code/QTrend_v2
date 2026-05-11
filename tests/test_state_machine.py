"""Tests for StateMachine."""

from __future__ import annotations

import pandas as pd

from qtrend_v2.state_machine import StateMachine
from qtrend_v2.types import ActionKind


def _bar(ts: str, close: float, rsi: float = 50.0) -> dict:
    return {"timestamp": pd.Timestamp(ts), "close": close, "rsi2": rsi, "atr": 30.0}


def test_buy_when_target_greater_than_current():
    sm = StateMachine()
    action = sm.step(target_lots=2, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    assert action.kind == ActionKind.BUY
    assert action.lots == 2


def test_hold_when_current_matches_target():
    sm = StateMachine()
    sm.step(target_lots=2, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-02 10:00"), kind=ActionKind.BUY, lots=2, price=3500.0
    )
    action = sm.step(target_lots=2, **_bar("2024-01-02 11:00", close=3510, rsi=55))
    assert action.kind == ActionKind.HOLD


def test_sell_when_target_below_current():
    sm = StateMachine()
    sm.step(target_lots=3, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-02 10:00"), kind=ActionKind.BUY, lots=3, price=3500.0
    )
    action = sm.step(target_lots=1, **_bar("2024-01-03 10:00", close=3520, rsi=60))
    assert action.kind == ActionKind.SELL
    assert action.lots == 2


def test_trailing_stop_triggers_flat_all():
    sm = StateMachine(atr_multiplier=3.0)
    sm.step(target_lots=3, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-02 10:00"), kind=ActionKind.BUY, lots=3, price=3500.0
    )
    sm.step(target_lots=3, **_bar("2024-01-02 11:00", close=3700, rsi=55))
    action = sm.step(target_lots=3, **_bar("2024-01-02 12:00", close=3600, rsi=40))
    assert action.kind == ActionKind.FLAT_ALL


def test_force_flat_clears_all_legs():
    sm = StateMachine()
    sm.step(target_lots=2, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-02 10:00"), kind=ActionKind.BUY, lots=2, price=3500.0
    )
    action = sm.force_flat(timestamp=pd.Timestamp("2024-01-05 09:00"), reason="bias_off")
    assert action.kind == ActionKind.FLAT_ALL
    assert sm.current_lots == 0


def test_reset_clears_state():
    sm = StateMachine()
    sm.step(target_lots=2, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-02 10:00"), kind=ActionKind.BUY, lots=2, price=3500.0
    )
    sm.reset()
    assert sm.current_lots == 0
    assert sm._peak_close is None


def test_buy_timing_filter_respects_rsi():
    """When RSI(2) >= 50 and we want to BUY, the action defers (HOLD)
    until either (a) RSI drops below 50 or (b) K bars elapse."""
    sm = StateMachine(timing_K_bars=3)
    a1 = sm.step(target_lots=2, **_bar("2024-01-02 10:00", close=3500, rsi=70))
    assert a1.kind == ActionKind.HOLD
    a2 = sm.step(target_lots=2, **_bar("2024-01-02 11:00", close=3500, rsi=80))
    assert a2.kind == ActionKind.HOLD
    a3 = sm.step(target_lots=2, **_bar("2024-01-02 12:00", close=3500, rsi=75))
    assert a3.kind == ActionKind.BUY
    assert a3.lots == 2
