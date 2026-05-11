"""Simulator adapter: fills at next 1H bar's open with fixed cost."""

from __future__ import annotations

import pandas as pd

from qtrend_v2.types import Action, ActionKind, Fill


class SimulatorAdapter:
    """Naive simulator. Fills at next 1H bar's open price. Adds tx_cost_per_lot
    to BUY fill price and subtracts from SELL fill price. Returns None for
    HOLD or when no next bar is available (end of window)."""

    def __init__(self, bars: pd.DataFrame, tx_cost_per_lot: float = 1.0):
        if "open" not in bars.columns:
            raise ValueError("simulator bars must have 'open' column")
        if not bars.index.is_monotonic_increasing:
            raise ValueError("simulator bars index must be monotonic increasing")
        self._bars = bars
        self.tx_cost_per_lot = tx_cost_per_lot

    def execute(self, *, action: Action, current_ts: pd.Timestamp) -> Fill | None:
        if action.kind == ActionKind.HOLD:
            return None
        future = self._bars.loc[self._bars.index > current_ts]
        if future.empty:
            return None
        next_bar = future.iloc[0]
        next_ts = future.index[0]

        if action.kind == ActionKind.BUY:
            price = float(next_bar["open"]) + self.tx_cost_per_lot
        elif action.kind == ActionKind.SELL:
            price = float(next_bar["open"]) - self.tx_cost_per_lot
        elif action.kind == ActionKind.FLAT_ALL:
            price = float(next_bar["open"]) - self.tx_cost_per_lot
        else:
            raise ValueError(f"unknown action {action.kind}")

        return Fill(
            timestamp=next_ts,
            kind=action.kind,
            lots=action.lots,
            price=price,
            reason=action.reason,
        )
