"""One-shot demo: merge Excel HC data onto the parquet base, run the strategy
over the most-recent 2 months, render the report, and open it in the browser.

Excel files expected on Desktop:
    ~/Desktop/HC.SHF(2).xlsx          1H bars 2026-03-12 → 2026-05-08
    ~/Desktop/HC.SHF 5min(1).xlsx     (not used here — QTrend_v2 is daily + 1H)

Parquet base:
    ~/Desktop/data/CN/market/continuous/.cache/HC_daily.parquet  (...→ 2026-02-24)
    ~/Desktop/data/CN/market/continuous/.cache/HC_60min.parquet  (...→ 2026-02-24)

A ~2-week gap (2026-02-25 → 2026-03-11) sits between the two sources — we
splice without forward-filling so the gap shows up honestly in the chart.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd

from qtrend_v2 import Strategy
from qtrend_v2.bias import BiasWindow
from qtrend_v2.data import load_hc_1h, load_hc_daily
from qtrend_v2.report import render_window_report

EXCEL_1H = Path("/Users/simon/Desktop/HC.SHF(2).xlsx")
REPORT_OUT = Path(__file__).parent.parent / "reports" / "demo_2026-03-12_to_2026-05-08.html"

# Map Chinese Wind column names to canonical OHLCV.
EXCEL_COLUMN_MAP = {
    "日期": "datetime",
    "开盘价(元)": "open",
    "最高价(元)": "high",
    "最低价(元)": "low",
    "收盘价(元)": "close",
    "成交量": "volume",
}


def load_excel_1h(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path).dropna(subset=["日期"])
    df = raw.rename(columns=EXCEL_COLUMN_MAP)[
        ["datetime", "open", "high", "low", "close", "volume"]
    ]
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime").sort_index()
    # The Wind 1H bars span the SHFE session windows (incl. night session at
    # 22-23h, 0-2h next day). Strategy treats them as a single monotonic series.
    return df


def main() -> None:
    daily_parquet = load_hc_daily()
    h1_parquet = load_hc_1h()
    h1_excel = load_excel_1h(EXCEL_1H)

    # Splice: parquet up to its last day, then Excel after.
    cutover = h1_parquet.index.max()
    h1_excel_new = h1_excel.loc[h1_excel.index > cutover]
    h1_combined = pd.concat([h1_parquet, h1_excel_new]).sort_index()
    h1_combined = h1_combined[~h1_combined.index.duplicated(keep="first")]

    # Daily comes from parquet base + Excel-resampled tail.
    daily_excel = (
        h1_excel_new.resample("1D")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["close"])
    )
    daily_combined = pd.concat([daily_parquet, daily_excel]).sort_index()
    daily_combined = daily_combined[~daily_combined.index.duplicated(keep="first")]

    print(
        f"Daily: {len(daily_combined)} bars, "
        f"{daily_combined.index.min().date()} → {daily_combined.index.max().date()}"
    )
    print(
        f"1H:    {len(h1_combined)} bars, " f"{h1_combined.index.min()} → {h1_combined.index.max()}"
    )

    # Demo window: the entire Excel period. NOTE — this is NOT a real Simon-annotated
    # bias window; it's just a demo span to show how the report looks. Replace with
    # the real bias_windows.csv entry before drawing any conclusions.
    window = BiasWindow(
        start=pd.Timestamp("2026-03-12"),
        end=pd.Timestamp("2026-05-08"),
        note="DEMO: latest 2-month span from Excel (NOT a real Simon-annotated bias window)",
    )

    strat = Strategy()
    result = strat.run_window(window=window, daily=daily_combined, h1=h1_combined)

    print(
        f"Actions: {len(result.actions_log)} | "
        f"Final PnL: {result.equity.iloc[-1] if len(result.equity) else 0:+.2f} | "
        f"Max lots reached: {result.lot_history.max() if len(result.lot_history) else 0}"
    )

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    render_window_report(result=result, daily=daily_combined, output_path=REPORT_OUT)
    print(f"Report written: {REPORT_OUT}")

    subprocess.run(["open", str(REPORT_OUT)], check=False)


if __name__ == "__main__":
    main()
