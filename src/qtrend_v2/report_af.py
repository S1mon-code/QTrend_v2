"""AlphaForge HTMLReportGenerator integration for QTrend_v2.

Bridges `WindowResult` (1H per-lot PnL series + actions log) to AlphaForge's
`BacktestResult` (RMB equity + daily returns + raw-fill trades schema) and
renders an institutional-grade report via `HTMLReportGenerator.generate()`.

## Why this exists
The spec (§3) called for reusing alphaforge.report. The v1 plan deviated and
shipped a basic in-house renderer in `qtrend_v2.report`. This module closes
that gap as part of v1.1.

## Capital base & multiplier semantics
QTrend_v2's `WindowResult.equity` is **per-lot price change**, denominated in
the underlying instrument's quote unit (RMB/ton for HC). To produce a proper
RMB equity curve we apply:

    equity_rmb(t) = initial_capital + WindowResult.equity(t) × multiplier

For HC: multiplier = 10 tons/lot (SHFE熱卷标准合约).

## Trades schema
AlphaForge's `_resolve_trades` expects a raw-fill log with columns:
    datetime, symbol, side (int ±1), lots, price, commission,
    slippage_cost, trading_day, is_close_today
We map each action_log row to one Trade and let alphaforge compute round-trips
internally via TradeLog.

## Requirements
- `alphaforge` must be importable. Install:
    pip install -e /Users/simon/Desktop/AlphaForge
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from qtrend_v2.backtest import WindowResult

# Default HC.SHF parameters. For other instruments, pass an InstrumentSpec.
_HC_MULTIPLIER = 10.0  # tons per lot
_HC_COMMISSION_RATE = 0.0001  # ratio of notional, per side
_DEFAULT_INITIAL_CAPITAL = 1_000_000.0


@dataclass(frozen=True)
class InstrumentSpec:
    """Minimal contract-spec snapshot used by the adapter."""

    symbol: str
    multiplier: float
    commission_rate: float

    @classmethod
    def hc(cls) -> InstrumentSpec:
        return cls(symbol="HC", multiplier=_HC_MULTIPLIER, commission_rate=_HC_COMMISSION_RATE)


def _require_alphaforge():
    """Import alphaforge lazily and raise a helpful message if unavailable."""
    try:
        from alphaforge.engine.result import BacktestResult
        from alphaforge.report.generator import HTMLReportGenerator
    except ImportError as exc:
        raise ImportError(
            "alphaforge is required for qtrend_v2.report_af. "
            "Install with: pip install -e /Users/simon/Desktop/AlphaForge"
        ) from exc
    return BacktestResult, HTMLReportGenerator


def _build_trades_df(
    actions_log: pd.DataFrame,
    spec: InstrumentSpec,
) -> pd.DataFrame | None:
    """Map QTrend_v2 actions_log to AlphaForge raw-fill trades schema."""
    if actions_log.empty:
        return None

    rows = []
    for _, row in actions_log.iterrows():
        kind = row["kind"]
        if kind not in ("BUY", "SELL", "FLAT_ALL"):
            continue
        side = 1 if kind == "BUY" else -1
        price = float(row["price"])
        lots = int(row["lots"])
        notional = price * lots * spec.multiplier
        rows.append(
            {
                "datetime": pd.Timestamp(row["ts"]),
                "symbol": spec.symbol,
                "side": side,
                "lots": lots,
                "price": price,
                "commission": notional * spec.commission_rate,
                "slippage_cost": 0.0,
                "trading_day": pd.Timestamp(row["ts"]).normalize(),
                "is_close_today": False,
            }
        )
    return pd.DataFrame(rows) if rows else None


def to_backtest_result(
    window_result: WindowResult,
    *,
    initial_capital: float = _DEFAULT_INITIAL_CAPITAL,
    spec: InstrumentSpec | None = None,
):
    """Convert WindowResult → AlphaForge BacktestResult.

    Args:
        window_result: QTrend_v2 single-window backtest result.
        initial_capital: Starting RMB capital, used to compute return%.
        spec: Instrument multiplier + commission. Defaults to HC.
    """
    BacktestResult, _ = _require_alphaforge()
    spec = spec or InstrumentSpec.hc()

    # 1) Build daily RMB equity curve.
    if len(window_result.equity) == 0:
        eq_daily = pd.Series([initial_capital], index=[window_result.window.start], name="equity")
        ret_daily = pd.Series([0.0], index=[window_result.window.start], name="ret")
    else:
        # equity is 1H PnL in price-units × lots; convert to RMB.
        pnl_rmb_1h = window_result.equity * spec.multiplier
        equity_rmb_1h = initial_capital + pnl_rmb_1h
        eq_daily = equity_rmb_1h.resample("1D").last().dropna()
        ret_daily = eq_daily.pct_change().fillna(0.0)

    # 2) Build trades log.
    trades_df = _build_trades_df(window_result.actions_log, spec)

    return BacktestResult(
        strategy_name=f"QTrend_v2 ({spec.symbol}, EWMAC(16,64)+Connors+3xATR)",
        equity_curve=eq_daily,
        daily_returns=ret_daily,
        trades=trades_df,
        metadata={
            "window_start": str(window_result.window.start.date()),
            "window_end": str(window_result.window.end.date()),
            "window_note": window_result.window.note,
            "instrument": spec.symbol,
            "multiplier": spec.multiplier,
            "initial_capital": initial_capital,
        },
    )


def render_alphaforge_report(
    *,
    window_result: WindowResult,
    output_path: str | Path,
    initial_capital: float = _DEFAULT_INITIAL_CAPITAL,
    spec: InstrumentSpec | None = None,
    freq: str = "daily",
) -> Path:
    """Render an AlphaForge HTML report for a QTrend_v2 window.

    Args:
        window_result: Single-window backtest result.
        output_path: Destination .html file.
        initial_capital: Starting RMB capital (default 1M).
        spec: Instrument spec (default HC: multiplier=10, commission=0.01%).
        freq: Chart frequency label (default "daily").
    """
    _, HTMLReportGenerator = _require_alphaforge()
    spec = spec or InstrumentSpec.hc()

    af_result = to_backtest_result(window_result, initial_capital=initial_capital, spec=spec)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gen = HTMLReportGenerator()
    gen.generate(
        result=af_result,
        output_path=str(output_path),
        freq=freq,
    )
    return output_path
