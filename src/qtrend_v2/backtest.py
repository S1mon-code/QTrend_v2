"""Backtest driver: run strategy over a single bias window."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from qtrend_v2.bias import BiasWindow
from qtrend_v2.execution.simulator import SimulatorAdapter
from qtrend_v2.forecast.base import ForecastSignal
from qtrend_v2.pullback.connors import ConnorsPullback
from qtrend_v2.sizing import Sizer
from qtrend_v2.state_machine import StateMachine
from qtrend_v2.types import Action, ActionKind


def _wilder_atr(daily: pd.DataFrame, period: int = 20) -> pd.Series:
    high = daily["high"].astype(float)
    low = daily["low"].astype(float)
    close = daily["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def _wilder_rsi(close: pd.Series, period: int = 2) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    roll_dn = down.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = roll_up / roll_dn
        rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


@dataclass
class WindowResult:
    window: BiasWindow
    equity: pd.Series  # cumulative PnL indexed by 1H timestamp
    actions_log: pd.DataFrame  # columns: ts, kind, lots, price, reason, current_lots
    lot_history: pd.Series  # current_lots over 1H bars
    forecast_history: pd.Series  # forecast over daily bars


def run_window(
    *,
    window: BiasWindow,
    daily: pd.DataFrame,
    h1: pd.DataFrame,
    forecast: ForecastSignal,
    sizer: Sizer,
    pullback: ConnorsPullback,
    state_machine: StateMachine,
    simulator: SimulatorAdapter,
) -> WindowResult:
    """Run strategy through one bias window. Returns WindowResult."""
    daily_window = daily.loc[window.start : window.end]
    h1_window = h1.loc[window.start : window.end]

    if daily_window.empty or h1_window.empty:
        return WindowResult(
            window=window,
            equity=pd.Series(dtype=float),
            actions_log=pd.DataFrame(),
            lot_history=pd.Series(dtype=int),
            forecast_history=pd.Series(dtype=float),
        )

    daily_full = daily.loc[: window.end]
    forecast_full = forecast.compute(daily_full)
    atr_full = _wilder_atr(daily_full)
    rsi_h1 = _wilder_rsi(h1.loc[: window.end]["close"])

    sizer.reset()
    pullback.reset()
    state_machine.reset()

    actions: list[dict] = []
    lot_history: list[tuple[pd.Timestamp, int]] = []
    pnl_series: list[tuple[pd.Timestamp, float]] = []
    cash = 0.0
    last_price = float(h1_window.iloc[0]["close"])

    for ts in h1_window.index:
        daily_ts = forecast_full.index[forecast_full.index <= ts]
        if daily_ts.empty:
            continue
        d_ts = daily_ts[-1]
        current_forecast = float(forecast_full.loc[d_ts])
        current_atr = float(atr_full.loc[d_ts]) if not np.isnan(atr_full.loc[d_ts]) else 50.0

        natural_target = sizer.update(forecast=current_forecast)
        modulated_target = pullback.adjust(
            h1_bars=h1.loc[:ts],
            current_forecast=current_forecast,
            current_target=natural_target,
        )

        close = float(h1_window.loc[ts]["close"])
        rsi2 = float(rsi_h1.loc[ts]) if ts in rsi_h1.index else 50.0

        action = state_machine.step(
            timestamp=ts,
            close=close,
            rsi2=rsi2,
            atr=current_atr,
            target_lots=modulated_target,
        )

        if action.kind in (ActionKind.BUY, ActionKind.SELL):
            fill = simulator.execute(action=action, current_ts=ts)
            if fill is not None:
                state_machine.record_fill(
                    timestamp=fill.timestamp,
                    kind=fill.kind,
                    lots=fill.lots,
                    price=fill.price,
                )
                signed = fill.lots if fill.kind == ActionKind.BUY else -fill.lots
                cash -= signed * fill.price
                actions.append(
                    {
                        "ts": fill.timestamp,
                        "kind": fill.kind.value,
                        "lots": fill.lots,
                        "price": fill.price,
                        "reason": fill.reason,
                        "current_lots": state_machine.current_lots,
                    }
                )
        elif action.kind == ActionKind.FLAT_ALL:
            lots_to_close = state_machine.current_lots
            if lots_to_close > 0:
                sell_action = Action(kind=ActionKind.SELL, lots=lots_to_close, reason=action.reason)
                fill = simulator.execute(action=sell_action, current_ts=ts)
                if fill is not None:
                    state_machine.record_fill(
                        timestamp=fill.timestamp,
                        kind=fill.kind,
                        lots=fill.lots,
                        price=fill.price,
                    )
                    cash += fill.lots * fill.price
                    actions.append(
                        {
                            "ts": fill.timestamp,
                            "kind": "FLAT_ALL",
                            "lots": fill.lots,
                            "price": fill.price,
                            "reason": action.reason,
                            "current_lots": 0,
                        }
                    )

        equity = cash + state_machine.current_lots * close
        pnl_series.append((ts, equity))
        lot_history.append((ts, state_machine.current_lots))
        last_price = close

    if state_machine.current_lots > 0:
        lots_to_close = state_machine.current_lots
        cash += lots_to_close * last_price
        state_machine.force_flat(timestamp=h1_window.index[-1], reason="bias_off")
        actions.append(
            {
                "ts": h1_window.index[-1],
                "kind": "FLAT_ALL",
                "lots": lots_to_close,
                "price": last_price,
                "reason": "bias_off_end_of_window",
                "current_lots": 0,
            }
        )

    equity_series = pd.Series(
        [p for _, p in pnl_series],
        index=pd.DatetimeIndex([t for t, _ in pnl_series]),
        name="equity",
    )
    lot_series = pd.Series(
        [lot for _, lot in lot_history],
        index=pd.DatetimeIndex([t for t, _ in lot_history]),
        name="lots",
    )
    actions_df = (
        pd.DataFrame(actions)
        if actions
        else pd.DataFrame(columns=["ts", "kind", "lots", "price", "reason", "current_lots"])
    )

    return WindowResult(
        window=window,
        equity=equity_series,
        actions_log=actions_df,
        lot_history=lot_series,
        forecast_history=forecast_full.loc[window.start : window.end],
    )
