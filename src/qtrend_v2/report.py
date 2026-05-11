"""HTML report generation: per-window + aggregate."""

from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd
from jinja2 import Template

from qtrend_v2.backtest import WindowResult

_WINDOW_TEMPLATE = Template(
    """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>QTrend_v2 — {{ start }} to {{ end }}</title>
<style>
body { font-family: -apple-system, sans-serif; max-width: 1100px; margin: 2em auto; }
table { border-collapse: collapse; }
th, td { padding: 4px 8px; border-bottom: 1px solid #ddd; text-align: left; }
img { display: block; margin: 1em 0; max-width: 100%; }
.note { background: #fff8c5; padding: 0.5em 1em; border-left: 4px solid #d4a017; }
</style></head>
<body>
<h1>QTrend_v2 — Bias window report</h1>
<p><strong>Window:</strong> {{ start }} → {{ end }}</p>
<div class="note"><strong>Note:</strong> {{ note }}</div>
<h2>Summary</h2>
<table>
<tr><th>Final PnL</th><td>{{ final_pnl }}</td></tr>
<tr><th>Max drawdown</th><td>{{ max_dd }}</td></tr>
<tr><th>Number of actions</th><td>{{ n_actions }}</td></tr>
<tr><th>Avg lots while in market</th><td>{{ avg_lots }}</td></tr>
</table>
<h2>Price + lots</h2>
<img src="data:image/png;base64,{{ chart_price_lots }}">
<h2>Equity curve</h2>
<img src="data:image/png;base64,{{ chart_equity }}">
<h2>Forecast</h2>
<img src="data:image/png;base64,{{ chart_forecast }}">
<h2>Action log</h2>
{{ actions_html | safe }}
</body></html>"""
)


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def render_window_report(
    *,
    result: WindowResult,
    daily: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    eq = result.equity
    final_pnl = float(eq.iloc[-1]) if len(eq) else 0.0
    running_max = eq.cummax() if len(eq) else eq
    drawdown = (eq - running_max) if len(eq) else eq
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    n_actions = int(result.actions_log.shape[0])
    in_market = result.lot_history[result.lot_history > 0]
    avg_lots = float(in_market.mean()) if len(in_market) else 0.0

    daily_slice = daily.loc[result.window.start : result.window.end]

    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax1.plot(daily_slice.index, daily_slice["close"], color="black", label="close")
    ax1.set_ylabel("close")
    ax2 = ax1.twinx()
    if len(result.lot_history):
        ax2.step(
            result.lot_history.index,
            result.lot_history.values,
            color="steelblue",
            where="post",
            label="lots",
            alpha=0.6,
        )
        ax2.set_ylabel("lots")
        ax2.set_ylim(-0.5, 5.5)
    ax1.set_title("Price + lot history")
    chart_price_lots = _fig_to_b64(fig)

    fig, ax = plt.subplots(figsize=(10, 3))
    if len(eq):
        ax.plot(eq.index, eq.values, color="darkgreen")
        ax.fill_between(eq.index, eq.values, eq.cummax(), color="red", alpha=0.2)
    ax.set_title("Equity (cumulative PnL)")
    chart_equity = _fig_to_b64(fig)

    fig, ax = plt.subplots(figsize=(10, 3))
    if len(result.forecast_history):
        ax.plot(result.forecast_history.index, result.forecast_history.values, color="purple")
        ax.axhspan(0, 4, color="grey", alpha=0.05, label="0 lots")
        ax.axhspan(4, 8, color="yellow", alpha=0.05)
        ax.axhspan(8, 12, color="orange", alpha=0.05)
        ax.axhspan(12, 16, color="red", alpha=0.05)
        ax.axhspan(16, 20, color="darkred", alpha=0.05)
        ax.set_ylim(0, 20)
        ax.set_title("Forecast (with sizing buckets)")
    chart_forecast = _fig_to_b64(fig)

    actions_html = (
        result.actions_log.to_html(index=False)
        if not result.actions_log.empty
        else "<p>(no actions taken)</p>"
    )

    html = _WINDOW_TEMPLATE.render(
        start=result.window.start.date(),
        end=result.window.end.date(),
        note=result.window.note,
        final_pnl=f"{final_pnl:+.2f}",
        max_dd=f"{max_dd:+.2f}",
        n_actions=n_actions,
        avg_lots=f"{avg_lots:.2f}",
        chart_price_lots=chart_price_lots,
        chart_equity=chart_equity,
        chart_forecast=chart_forecast,
        actions_html=actions_html,
    )
    output_path.write_text(html)
    return output_path


_AGGREGATE_TEMPLATE = Template(
    """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>QTrend_v2 — Aggregate</title>
<style>
body { font-family: -apple-system, sans-serif; max-width: 1100px; margin: 2em auto; }
table { border-collapse: collapse; }
th, td { padding: 4px 8px; border-bottom: 1px solid #ddd; text-align: left; }
img { display: block; margin: 1em 0; max-width: 100%; }
</style></head>
<body>
<h1>QTrend_v2 — Aggregate report (across {{ n }} windows)</h1>
<h2>Per-window summary</h2>
{{ per_window_html | safe }}
<h2>Aggregate metrics</h2>
<table>
<tr><th>Hit rate (% positive)</th><td>{{ hit_rate }}</td></tr>
<tr><th>Total PnL</th><td>{{ total_pnl }}</td></tr>
<tr><th>Mean per-window PnL</th><td>{{ mean_pnl }}</td></tr>
<tr><th>Worst-window drawdown</th><td>{{ worst_dd }}</td></tr>
<tr><th>Median time-in-market</th><td>{{ median_tim }}</td></tr>
</table>
<h2>PnL distribution</h2>
<img src="data:image/png;base64,{{ chart_pnl_dist }}">
</body></html>"""
)


def render_aggregate_report(
    *,
    results: list[WindowResult],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for r in results:
        eq = r.equity
        pnl = float(eq.iloc[-1]) if len(eq) else 0.0
        dd = float((eq - eq.cummax()).min()) if len(eq) else 0.0
        in_market = r.lot_history[r.lot_history > 0]
        tim = float(len(in_market) / len(r.lot_history)) if len(r.lot_history) else 0.0
        rows.append(
            {
                "start": r.window.start.date(),
                "end": r.window.end.date(),
                "note": r.window.note,
                "pnl": round(pnl, 2),
                "max_dd": round(dd, 2),
                "time_in_market": round(tim, 3),
                "n_actions": int(r.actions_log.shape[0]),
            }
        )

    summary = pd.DataFrame(rows)
    hit_rate = (summary["pnl"] > 0).mean() if len(summary) else 0.0
    total_pnl = summary["pnl"].sum() if len(summary) else 0.0
    mean_pnl = summary["pnl"].mean() if len(summary) else 0.0
    worst_dd = summary["max_dd"].min() if len(summary) else 0.0
    median_tim = summary["time_in_market"].median() if len(summary) else 0.0

    fig, ax = plt.subplots(figsize=(8, 3))
    if len(summary):
        ax.bar(
            range(len(summary)),
            summary["pnl"],
            color=["green" if p > 0 else "red" for p in summary["pnl"]],
        )
        ax.axhline(0, color="black", linewidth=0.5)
        ax.set_xticks(range(len(summary)))
        ax.set_xticklabels(summary["note"], rotation=30, ha="right")
        ax.set_ylabel("PnL")
        ax.set_title("Per-window PnL")
    chart_pnl_dist = _fig_to_b64(fig)

    html = _AGGREGATE_TEMPLATE.render(
        n=len(results),
        per_window_html=summary.to_html(index=False) if len(summary) else "<p>(no windows)</p>",
        hit_rate=f"{hit_rate:.1%}",
        total_pnl=f"{total_pnl:+.2f}",
        mean_pnl=f"{mean_pnl:+.2f}",
        worst_dd=f"{worst_dd:+.2f}",
        median_tim=f"{median_tim:.1%}",
        chart_pnl_dist=chart_pnl_dist,
    )
    output_path.write_text(html)
    return output_path
