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


def test_sell_timing_filter_respects_rsi():
    """Mirror of buy filter for the sell path: when RSI < sell_rsi_min,
    SELL is deferred until either RSI recovers or K bars elapse."""
    sm = StateMachine(timing_K_bars=3)
    sm.step(target_lots=3, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-02 10:00"), kind=ActionKind.BUY, lots=3, price=3500.0
    )
    # Now ask to scale down with RSI well below sell_rsi_min=50 — must defer.
    a1 = sm.step(target_lots=1, **_bar("2024-01-03 10:00", close=3520, rsi=30))
    assert a1.kind == ActionKind.HOLD
    a2 = sm.step(target_lots=1, **_bar("2024-01-03 11:00", close=3520, rsi=25))
    assert a2.kind == ActionKind.HOLD
    a3 = sm.step(target_lots=1, **_bar("2024-01-03 12:00", close=3520, rsi=20))
    # K=3 bars elapsed — must fire SELL even though RSI still bad.
    assert a3.kind == ActionKind.SELL
    assert a3.lots == 2


def test_record_fill_sell_to_zero_resets_round():
    """When record_fill SELL takes us to 0, _end_round must clear peak."""
    sm = StateMachine()
    sm.step(target_lots=2, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-02 10:00"), kind=ActionKind.BUY, lots=2, price=3500.0
    )
    assert sm._peak_close == 3500.0
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-03 10:00"), kind=ActionKind.SELL, lots=2, price=3520.0
    )
    assert sm.current_lots == 0
    assert sm._peak_close is None  # round ended


def test_record_fill_buy_preserves_higher_peak():
    """A later BUY at a lower price must not lower _peak_close."""
    sm = StateMachine()
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-02 10:00"), kind=ActionKind.BUY, lots=1, price=3700.0
    )
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-03 10:00"), kind=ActionKind.BUY, lots=1, price=3600.0
    )
    assert sm._peak_close == 3700.0


def test_record_fill_partial_sell_fifo():
    """SELL of fewer lots than oldest leg must trim that leg, preserve newer."""
    sm = StateMachine()
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-02 10:00"), kind=ActionKind.BUY, lots=3, price=3500.0
    )
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-03 10:00"), kind=ActionKind.BUY, lots=2, price=3600.0
    )
    sm.record_fill(
        timestamp=pd.Timestamp("2024-01-04 10:00"), kind=ActionKind.SELL, lots=4, price=3700.0
    )
    # 4 sold FIFO: full first leg (3) + 1 from second leg → 1 lot at 3600 remaining.
    assert sm.current_lots == 1
    assert len(sm._legs) == 1
    assert sm._legs[0].price == 3600.0
    assert sm._legs[0].lots == 1


def test_force_flat_when_already_flat_returns_hold():
    """Calling force_flat with no position must return HOLD with explanatory reason."""
    sm = StateMachine()
    action = sm.force_flat(timestamp=pd.Timestamp("2024-01-02 10:00"), reason="bias_off")
    assert action.kind == ActionKind.HOLD
    assert "flat_already" in action.reason
