"""Demo: splice Excel HC 1H onto parquet base, run Strategy, render via the
proper qtrend_v2.report_af adapter (institutional-grade AlphaForge HTML).

Replaces the earlier inline hack with the canonical adapter from
src/qtrend_v2/report_af.py.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd

from qtrend_v2 import Strategy
from qtrend_v2.bias import BiasWindow
from qtrend_v2.data import load_hc_1h, load_hc_daily
from qtrend_v2.report_af import InstrumentSpec, render_alphaforge_report

EXCEL_1H = Path("/Users/simon/Desktop/HC.SHF(2).xlsx")
REPORT_OUT = (
    Path(__file__).parent.parent / "reports" / "demo_alphaforge_2026-03-12_to_2026-05-08.html"
)

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
    return df.set_index("datetime").sort_index()


def _enrich_with_metadata_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Fill in the parquet-schema columns missing from Excel-sourced bars.

    Excel gives bare OHLCV. Parquet schema (and AlphaForge BarArray) also expects:
    open_raw/high_raw/low_raw/close_raw/origin_symbol/factor/is_rollover (+ amount/oi/
    trading_day). For Excel data we treat the OHLC as already-raw (no back-adjustment),
    so raw cols mirror their adjusted siblings and factor=1.0.
    """
    df = df.copy()
    for col, raw_col in (
        ("open", "open_raw"),
        ("high", "high_raw"),
        ("low", "low_raw"),
        ("close", "close_raw"),
    ):
        if raw_col not in df.columns:
            df[raw_col] = df[col]
    if "factor" not in df.columns:
        df["factor"] = 1.0
    if "is_rollover" not in df.columns:
        df["is_rollover"] = False
    if "origin_symbol" not in df.columns:
        df["origin_symbol"] = "HC.SHF"
    if "amount" not in df.columns:
        df["amount"] = 0.0
    if "oi" not in df.columns:
        df["oi"] = 0.0
    if "trading_day" not in df.columns:
        df["trading_day"] = df.index.normalize()
    return df


def splice_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_parquet = load_hc_daily()
    h1_parquet = load_hc_1h()
    h1_excel = load_excel_1h(EXCEL_1H)
    h1_excel = _enrich_with_metadata_cols(h1_excel)

    cutover = h1_parquet.index.max()
    h1_excel_new = h1_excel.loc[h1_excel.index > cutover]
    h1 = pd.concat([h1_parquet, h1_excel_new]).sort_index()
    h1 = h1[~h1.index.duplicated(keep="first")]

    daily_excel = (
        h1_excel_new.resample("1D")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "amount": "sum",
                "open_raw": "first",
                "high_raw": "max",
                "low_raw": "min",
                "close_raw": "last",
                "factor": "first",
                "is_rollover": "max",
                "origin_symbol": "first",
            }
        )
        .dropna(subset=["close"])
    )
    daily_excel["oi"] = 0.0
    daily_excel["trading_day"] = daily_excel.index.normalize()
    daily = pd.concat([daily_parquet, daily_excel]).sort_index()
    daily = daily[~daily.index.duplicated(keep="first")]
    return daily, h1


def main() -> None:
    daily, h1 = splice_data()
    print(f"Daily: {len(daily)} bars   1H: {len(h1)} bars")

    window = BiasWindow(
        start=pd.Timestamp("2026-03-12"),
        end=pd.Timestamp("2026-05-08"),
        note="DEMO span (latest Excel data) — NOT a real Simon-annotated bias window",
    )

    strat = Strategy()
    wr = strat.run_window(window=window, daily=daily, h1=h1)
    print(
        f"Actions: {len(wr.actions_log)} | "
        f"Per-lot PnL: {wr.equity.iloc[-1] if len(wr.equity) else 0:+.2f} | "
        f"Max lots: {wr.lot_history.max() if len(wr.lot_history) else 0}"
    )

    # Slice bars to window + 3-month warmup for a readable K-line chart.
    warmup_start = window.start - pd.Timedelta(days=90)
    bars_for_chart = daily.loc[warmup_start : window.end]

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
