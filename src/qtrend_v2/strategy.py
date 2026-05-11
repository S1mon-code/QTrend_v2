"""Top-level Strategy: wires forecast, sizer, pullback, state_machine, simulator."""

from __future__ import annotations

import numpy as np
import pandas as pd

from qtrend_v2.backtest import _ATR_FALLBACK, WindowResult, _wilder_atr, _wilder_rsi, run_window
from qtrend_v2.bias import BiasWindow
from qtrend_v2.execution.simulator import SimulatorAdapter
from qtrend_v2.forecast.base import ForecastSignal
from qtrend_v2.forecast.ewmac import EWMAC
from qtrend_v2.pullback.connors import ConnorsPullback
from qtrend_v2.sizing import Sizer
from qtrend_v2.state_machine import StateMachine
from qtrend_v2.types import Action


class Strategy:
    """User-facing entry point. Default v1 config: EWMAC(16,64) + Connors + 3×ATR stop.

    Two operating modes:
      - `run_window()` — full-history backtest over a bias window
      - `signal()`     — single-bar advisory for live use; returns the next Action
                         given the current 1H timestamp and live position
    """

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

    def signal(
        self,
        *,
        daily_bars: pd.DataFrame,
        h1_bars: pd.DataFrame,
        current_lots: int,
    ) -> Action:
        """Advisory single-bar evaluation for live use.

        Caller passes the full daily and 1H history up to (and including) the
        current bar plus the broker-reported `current_lots`. Returns the next
        `Action` the state machine wants to take. Caller is responsible for
        executing the action externally and feeding the resulting fill back via
        `self.state_machine.record_fill(...)` before calling `signal()` again.

        Note: this method does NOT enforce a bias gate. Caller must only call it
        while Simon's `long bias` is ON; when bias is OFF, caller should call
        `self.state_machine.force_flat(...)` directly instead.
        """
        if h1_bars.empty:
            raise ValueError("h1_bars must contain at least one row")
        ts = h1_bars.index[-1]

        # Align state machine's internal lot count to broker truth. signal() is
        # advisory only — it returns intent, never records fills — so the
        # synthetic-leg rebuild below is the one place external state syncs in.
        if self.state_machine.current_lots != current_lots:
            from qtrend_v2.types import Leg

            last_close = float(h1_bars["close"].iloc[-1])
            if current_lots > 0:
                self.state_machine._legs = [  # noqa: SLF001
                    Leg(timestamp=ts, price=last_close, lots=current_lots)
                ]
                self.state_machine._peak_close = last_close  # noqa: SLF001
            else:
                self.state_machine._legs = []  # noqa: SLF001
                self.state_machine._peak_close = None  # noqa: SLF001

        forecast_series = self.forecast.compute(daily_bars)
        atr_series = _wilder_atr(daily_bars)
        rsi_h1_series = _wilder_rsi(h1_bars["close"])

        d_ts_candidates = forecast_series.index[forecast_series.index <= ts]
        if d_ts_candidates.empty:
            raise ValueError("daily_bars must contain at least one row at or before ts")
        d_ts = d_ts_candidates[-1]

        current_forecast = float(forecast_series.loc[d_ts])
        atr_value = atr_series.loc[d_ts]
        current_atr = float(atr_value) if not np.isnan(atr_value) else _ATR_FALLBACK
        rsi2 = float(rsi_h1_series.iloc[-1]) if len(rsi_h1_series) else 50.0

        natural_target = self.sizer.update(forecast=current_forecast)
        modulated_target = self.pullback.adjust(
            h1_bars=h1_bars,
            current_forecast=current_forecast,
            current_target=natural_target,
        )

        return self.state_machine.step(
            timestamp=ts,
            close=float(h1_bars["close"].iloc[-1]),
            rsi2=rsi2,
            atr=current_atr,
            target_lots=modulated_target,
        )
