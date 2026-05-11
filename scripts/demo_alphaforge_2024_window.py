"""Demo: run QTrend_v2 Strategy on the 2024-01-08 → 2024-04-10 bias window and
render an AlphaForge HTML report (now driven by TradingView Lightweight Charts
for the K-line section after the 2026-05-11 migration).

Picks the second bias window from data/bias_windows.csv (3-month span,
post-easing rally narrative) and runs the full chain:
    EWMAC(16, 64) forecast → Connors pullback → 3×ATR state machine.

Pure parquet — no Excel splice needed for this window.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from qtrend_v2 import Strategy
from qtrend_v2.bias import BiasWindowLoader
from qtrend_v2.data import load_hc_1h, load_hc_daily
from qtrend_v2.report_af import InstrumentSpec, render_alphaforge_report

BIAS_CSV = Path(__file__).parent.parent / "data" / "bias_windows.csv"
REPORT_OUT = (
    Path(__file__).parent.parent
    / "reports"
    / "demo_alphaforge_2024-01_to_2024-04.html"
)
# Index 1 in bias_windows.csv → 2024-01-08 to 2024-04-10
WINDOW_IDX = 1


def main() -> None:
    daily = load_hc_daily()
    h1 = load_hc_1h()
    print(f"Daily: {len(daily)} bars   1H: {len(h1)} bars")
    print(f"Span : {daily.index.min().date()} → {daily.index.max().date()}")

    windows = BiasWindowLoader(BIAS_CSV).windows()
    window = windows[WINDOW_IDX]
    print(
        f"Window: {window.start.date()} → {window.end.date()}\n  note: {window.note}"
    )

    strat = Strategy()
    wr = strat.run_window(window=window, daily=daily, h1=h1)
    last_eq = wr.equity.iloc[-1] if len(wr.equity) else 0.0
    max_lots = wr.lot_history.max() if len(wr.lot_history) else 0
    print(
        f"Actions: {len(wr.actions_log):3d} | "
        f"Per-lot PnL: {last_eq:+.2f} | "
        f"Max lots: {max_lots}"
    )

    # Show the chart with 60 trading days of warmup before window start.
    warmup_start = window.start - __import__("pandas").Timedelta(days=60)
    bars_for_chart = daily.loc[warmup_start : window.end]
    print(f"Chart  : {bars_for_chart.index.min().date()} → "
          f"{bars_for_chart.index.max().date()}  ({len(bars_for_chart)} bars)")

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    render_alphaforge_report(
        window_result=wr,
        output_path=REPORT_OUT,
        bars=bars_for_chart,
        initial_capital=1_000_000,
        spec=InstrumentSpec.hc(),
        freq="daily",
    )
    print(f"Report: {REPORT_OUT}")
    subprocess.run(["open", str(REPORT_OUT)], check=False)


if __name__ == "__main__":
    main()
