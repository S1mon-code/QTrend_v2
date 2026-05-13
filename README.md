# QTrend_v2

Long-only trend-capture engine for HC (热卷) futures. Carver-style continuous forecast → integer-lot sizing (0-5) → 1H Connors pullback modulator → ATR trailing stop. Driven by manually annotated `long bias` windows from Simon.

See:
- `docs/superpowers/specs/2026-05-11-qtrend-v2-design.md` — full design spec
- `docs/superpowers/plans/2026-05-11-qtrend-v2-implementation.md` — this plan
- `docs/research/2026-05-11-indicator-frequency-research.md` — indicator-frequency deep research

## Install (dev)
```
cd ~/Desktop/QTrend_v2
python -m pip install -e ".[dev]"
```

## Run tests
```
pytest -ra
```

## Status
- **v1.0 — shipped 2026-05-11**: 15 tasks, 50 tests, full backtest pipeline (HC daily + 1H, EWMAC forecast → 0-5 lot sizing → Connors pullback → 3×ATR trailing stop), end-to-end smoke on real data.
- **v1.1 — shipped 2026-05-11**: AlphaForge `HTMLReportGenerator` integration via `src/qtrend_v2/report_af.py` (+ 4 tests → 54 total). Closed the v1 spec deviation where reports were written in-house instead of via alphaforge as §3 originally specified. Reports render institutional-grade: TV-style K-line + entry/exit markers, equity vs. BH benchmark, drawdown, monthly heatmap, rolling Sharpe, trade table.
- **Current**: 54 tests passing, ruff clean. Real bias-window annotation by Simon remains the bottleneck before backtest output can be treated as meaningful (the 3 rows in `data/bias_windows.csv` are still PLACEHOLDERs).

See [docs/CHANGELOG.md](docs/CHANGELOG.md) for the full version history.

Out of scope (deferred): live execution (CTP/PythonGO), paper trade, quantitative bias proxy, multi-instrument.

## Reports

`scripts/demo_alphaforge_report.py` and `scripts/demo_alphaforge_2024_window.py` produce AlphaForge institutional-grade HTML reports via the bridge in `src/qtrend_v2/report_af.py`.

**2026-05-11**: QTrend_v2 was the demand driver for AlphaForge's K-line migration to **TradingView Lightweight Charts** v5.2.0 (Apache-2.0). The K-line section in every report is now TV-styled:
- Authentic TV candlestick + right-anchored price scale
- Real time-axis gaps over non-trading periods
- Trade markers `aboveBar` / `belowBar` (fill price + lots in hover text)
- Volume + indicator panes synchronized to one crosshair
- Other 10+ report sections (equity, drawdown, monthly heatmap, trades table, etc.) continue using Plotly — both libraries coexist in the same HTML

QTrend_v2 itself didn't change — same `HTMLReportGenerator.generate()` API consumption. The upgrade is internal to AlphaForge (`feature/kline-tv-lightweight-charts` branch off `0b897f9`).
