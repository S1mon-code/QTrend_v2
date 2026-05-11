"""Top-level Strategy: wires forecast, sizer, pullback, state_machine, simulator."""

from __future__ import annotations

import pandas as pd

from qtrend_v2.backtest import WindowResult, run_window
from qtrend_v2.bias import BiasWindow
from qtrend_v2.execution.simulator import SimulatorAdapter
from qtrend_v2.forecast.base import ForecastSignal
from qtrend_v2.forecast.ewmac import EWMAC
from qtrend_v2.pullback.connors import ConnorsPullback
from qtrend_v2.sizing import Sizer
from qtrend_v2.state_machine import StateMachine


class Strategy:
    """User-facing entry point. Default v1 config: EWMAC(16,64) + Connors + 3×ATR stop."""

    def __init__(
        self,
        forecast: ForecastSignal | None = None,
        sizer: Sizer | None = None,
        pullback: ConnorsPullback | None = None,
        state_machine: StateMachine | None = None,
        tx_cost_per_lot: float = 1.0,
    ):
        self.forecast = forecast or EWMAC()
        self.sizer = sizer or Sizer()
        self.pullback = pullback or ConnorsPullback()
        self.state_machine = state_machine or StateMachine()
        self.tx_cost_per_lot = tx_cost_per_lot

    def run_window(
        self,
        *,
        window: BiasWindow,
        daily: pd.DataFrame,
        h1: pd.DataFrame,
    ) -> WindowResult:
        sim = SimulatorAdapter(bars=h1, tx_cost_per_lot=self.tx_cost_per_lot)
        return run_window(
            window=window,
            daily=daily,
            h1=h1,
            forecast=self.forecast,
            sizer=self.sizer,
            pullback=self.pullback,
            state_machine=self.state_machine,
            simulator=sim,
        )
