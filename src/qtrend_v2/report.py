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
