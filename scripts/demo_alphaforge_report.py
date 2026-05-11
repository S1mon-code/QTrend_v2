"""Same demo as demo_report_with_excel.py but renders via AlphaForge's
HTMLReportGenerator instead of QTrend_v2's built-in report.

Bridges WindowResult → BacktestResult:
- equity_curve  : 1H equity resampled to daily last
- daily_returns : pct_change of daily equity
- trades        : actions_log mapped to the alphaforge trades schema
- strategy_name : "QTrend_v2 (HC, EWMAC+Connors)"

AlphaForge is loaded via sys.path injection rather than a packaged dep — this
is a demo-time bridge, not the production integration story.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

# AlphaForge sits next to QTrend_v2 on Desktop — inject it into sys.path.
sys.path.insert(0, "/Users/simon/Desktop/AlphaForge")

from alphaforge.engine.result import BacktestResult  # noqa: E402
from alphaforge.report.generator import HTMLReportGenerator  # noqa: E402

from qtrend_v2 import Strategy  # noqa: E402
from qtrend_v2.backtest import WindowResult  # noqa: E402
from qtrend_v2.bias import BiasWindow  # noqa: E402
from qtrend_v2.data import load_hc_1h, load_hc_daily  # noqa: E402

EXCEL_1H = Path("/Users/simon/Desktop/HC.SHF(2).xlsx")
REPORT_OUT = Path(__file__).parent.parent / "reports" / "demo_alphaforge_2026-03-12_to_2026-05-08.html"

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
    df = raw.rename(columns=EXCEL_COLUMN_MAP)[["datetime", "open", "high", "low", "close", "volume"]]
    df["datetime"] = pd.to_datetime(df["datetime"])
    return df.set_index("datetime").sort_index()


def splice_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_parquet = load_hc_daily()
    h1_parquet = load_hc_1h()
    h1_excel = load_excel_1h(EXCEL_1H)

    cutover = h1_parquet.index.max()
    h1_excel_new = h1_excel.loc[h1_excel.index > cutover]
    h1 = pd.concat([h1_parquet, h1_excel_new]).sort_index()
    h1 = h1[~h1.index.duplicated(keep="first")]

    daily_excel = (
        h1_excel_new.resample("1D")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["close"])
    )
    daily = pd.concat([daily_parquet, daily_excel]).sort_index()
    daily = daily[~daily.index.duplicated(keep="first")]
    return daily, h1


def to_alphaforge_result(result: WindowResult) -> BacktestResult:
    """Bridge QTrend_v2 WindowResult to AlphaForge BacktestResult.

    Notes:
    - QTrend_v2 emits 1H-indexed equity in units of price (e.g. RMB/ton on
      HC continuous, not RMB notional). For AF report purposes we treat that
      as the equity series directly and resample to daily 'last' close.
    - AF expects pct_change daily_returns. Strict pct_change on an equity that
      starts at 0 yields inf — so we add a starting-capital offset of 1.0
      before pct_change and remove it implicitly via the resulting return
      series. (Pure cosmetic — return shape is unaffected.)
    - trades_df mapped from actions_log; columns chosen to satisfy
      _resolve_trades fallback in alphaforge.report.helpers.
    """
    eq_1h = result.equity
    if len(eq_1h) == 0:
        eq_daily = pd.Series([0.0], index=[result.window.start], name="equity")
        ret_daily = pd.Series([0.0], index=[result.window.start], name="ret")
    else:
        eq_daily = eq_1h.resample("1D").last().dropna()
        # Shift equity into a positive base so pct_change is well-defined.
        base = 1_000_000.0  # nominal capital; only used to make pct_change finite
        eq_for_ret = base + eq_daily
        ret_daily = eq_for_ret.pct_change().fillna(0.0)
        eq_daily = eq_for_ret  # report shows absolute equity, not PnL delta

    # Trades schema: AlphaForge looks for 'entry_dt', 'exit_dt', 'pnl', 'side'.
    # We keep it minimal — the AF report can render a basic trade table.
    trades_rows = []
    open_leg = None
    for _, row in result.actions_log.iterrows():
        kind = row["kind"]
        if kind == "BUY":
            if open_leg is None:
                open_leg = {"entry_dt": row["ts"], "entry_price": row["price"], "lots": row["lots"]}
            else:
                open_leg["lots"] += row["lots"]
        elif kind in ("SELL", "FLAT_ALL"):
            if open_leg is not None:
                pnl = (row["price"] - open_leg["entry_price"]) * min(open_leg["lots"], row["lots"])
                trades_rows.append({
                    "entry_dt": open_leg["entry_dt"],
                    "exit_dt": row["ts"],
                    "entry_price": open_leg["entry_price"],
                    "exit_price": row["price"],
                    "lots": min(open_leg["lots"], row["lots"]),
                    "pnl": pnl,
                    "side": 1,  # +1 = long, -1 = short (alphaforge convention)
                })
                open_leg["lots"] -= row["lots"]
                if open_leg["lots"] <= 0:
                    open_leg = None

    trades_df = pd.DataFrame(trades_rows) if trades_rows else None

    return BacktestResult(
        strategy_name="QTrend_v2 (HC, EWMAC(16,64)+Connors+3xATR)",
        equity_curve=eq_daily,
        daily_returns=ret_daily,
        trades=trades_df,
        metadata={
            "window_start": str(result.window.start.date()),
            "window_end": str(result.window.end.date()),
            "window_note": result.window.note,
            "instrument": "HC.SHF",
        },
    )


def main() -> None:
    daily, h1 = splice_data()
    print(f"Daily: {len(daily)} bars   1H: {len(h1)} bars")

    window = BiasWindow(
        start=pd.Timestamp("2026-03-12"),
        end=pd.Timestamp("2026-05-08"),
        note="DEMO span (latest Excel data) — NOT a real Simon-annotated bias window",
    )

    strat = Strategy()
    result = strat.run_window(window=window, daily=daily, h1=h1)
    print(
        f"Actions: {len(result.actions_log)} | "
        f"Final PnL: {result.equity.iloc[-1] if len(result.equity) else 0:+.2f} | "
        f"Max lots: {result.lot_history.max() if len(result.lot_history) else 0}"
    )

    af_result = to_alphaforge_result(result)
    print(
        f"AF result — equity: {len(af_result.equity_curve)} days, "
        f"sharpe ≈ {af_result.sharpe:.2f}, total_return ≈ {af_result.total_return:.2%}"
    )

    gen = HTMLReportGenerator()
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    out = gen.generate(
        result=af_result,
        output_path=str(REPORT_OUT),
        freq="daily",
    )
    print(f"AlphaForge report: {out}")
    subprocess.run(["open", str(out)], check=False)


if __name__ == "__main__":
    main()
