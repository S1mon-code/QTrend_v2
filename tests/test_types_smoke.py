"""Verify shared types validate as expected."""

from __future__ import annotations

import pytest

from qtrend_v2.types import Action, ActionKind


def test_action_buy_requires_positive_lots():
    Action(kind=ActionKind.BUY, lots=2, reason="ok")  # no raise
    with pytest.raises(ValueError):
        Action(kind=ActionKind.BUY, lots=0, reason="bad")


def test_action_hold_requires_zero_lots():
    Action(kind=ActionKind.HOLD, lots=0, reason="ok")
    with pytest.raises(ValueError):
        Action(kind=ActionKind.HOLD, lots=1, reason="bad")


def test_action_flat_all_requires_zero_lots():
    Action(kind=ActionKind.FLAT_ALL, lots=0, reason="ok")
    with pytest.raises(ValueError):
        Action(kind=ActionKind.FLAT_ALL, lots=3, reason="bad")
