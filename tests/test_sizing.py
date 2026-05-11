"""Tests for forecast → integer lot sizing with hysteresis."""

from __future__ import annotations

from qtrend_v2.sizing import Sizer


def test_sizer_rising_thresholds():
    s = Sizer()
    assert s.update(forecast=0.0) == 0
    assert s.update(forecast=4.5) == 1
    assert s.update(forecast=8.5) == 2
    assert s.update(forecast=12.5) == 3
    assert s.update(forecast=16.5) == 4
    assert s.update(forecast=20.0) == 5


def test_sizer_falling_with_hysteresis():
    s = Sizer()
    s.update(forecast=20.0)
    assert s.update(forecast=19.5) == 5
    assert s.update(forecast=18.5) == 4
    assert s.update(forecast=15.5) == 4
    assert s.update(forecast=14.5) == 3


def test_sizer_reset_clears_state():
    s = Sizer()
    s.update(forecast=20.0)
    s.reset()
    assert s.update(forecast=4.5) == 1


def test_sizer_clips_negative_to_zero():
    s = Sizer()
    assert s.update(forecast=-3.0) == 0


def test_sizer_clips_above_max():
    s = Sizer()
    assert s.update(forecast=100.0) == 5
