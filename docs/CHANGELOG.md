# QTrend_v2 — CHANGELOG

Authoritative version history. Spec ([docs/superpowers/specs/](superpowers/specs/)) and plan ([docs/superpowers/plans/](superpowers/plans/)) are preserved as historical design / execution records. **This file is the single source of truth for current state.**

---

## v1.1 — AlphaForge report integration (shipped 2026-05-11)

**Why**: Closes a v1 spec deviation. The spec §3 said "reuse `alphaforge.report`", but the v1 plan shipped an in-house renderer (`src/qtrend_v2/report.py`) for fast iteration. Simon flagged this with "为什么不用 alphaforge 的 report" once v1 was running.

### What changed
- **New module** `src/qtrend_v2/report_af.py`: bridges QTrend_v2 `WindowResult` → AlphaForge `BacktestResult`, then renders via `HTMLReportGenerator.generate()`.
  - `InstrumentSpec.hc()` captures HC contract: multiplier=10 t/lot, commission=0.01% ratio (matches `~/Desktop/AlphaForge/alphaforge/data/specs.yaml`).
  - `to_backtest_result()` converts per-lot 1H PnL → daily RMB equity with proper capital base + `daily_returns` via `pct_change`.
  - Raw-fill trades schema: `datetime / symbol / side (±1) / lots / price / commission / slippage_cost / trading_day / is_close_today` — alphaforge round-trips internally via `TradeLog`.
  - `render_alphaforge_report(bars=...)` wraps a parquet-schema DataFrame into AlphaForge `BarArray` and passes it as `bar_data` + `spec_manager`; without this, K-line + trade markers are silently skipped.
  - **Daily-bar trade-marker alignment**: when `freq="daily"`, trade timestamps are normalised to midnight so alphaforge's strict-string `dt_to_idx` lookup matches the bar timestamps. (Without this fix, all entry/exit dots vanish from the K-line.)
- **pyproject.toml**: added `alphaforge @ file:///Users/simon/Desktop/AlphaForge` path-based dep.
- **Tests** (+4 → 54 total): `tests/test_report_af.py` — adapter contract, empty-window safety, raw-fill schema validation, render-to-disk smoke. All `skipif` when alphaforge isn't importable.
- **Demo scripts**:
  - `scripts/demo_alphaforge_report.py` — splices Excel HC 1H (latest 2 months) onto the parquet base, runs strategy, renders the proper AlphaForge report on the latest demo span.
  - `scripts/demo_alphaforge_2024_window.py` — pure parquet (no Excel splice), runs on the placeholder 2024-01-08 → 2024-04-10 bias window. Cleaner demo.

### Bug fixes done as part of v1.1
- `fix(report_af): K-line + trade markers now render` — two compounding bugs (no `bar_data` passed → Section 2.5 skipped; daily-vs-1H timestamp mismatch → markers silently dropped). Commit `ceeece3`.
- (From end of v1 sweep) `fix(pullback): restore RSI=100 on pure-up streaks` — earlier `_rsi` helper `replace(0, NaN)` masked the canonical 100 reading and silently disabled the trim trigger on monotonic uptrends. Commit `60f92c7`.
- (From end of v1 sweep) `fix(backtest): capture lots_before step() to avoid silent leg drop on trailing stop` — state machine clears legs inside `step()` before returning FLAT_ALL, so the backtest driver was reading 0 lots and never crediting cash. Commit `57a980c`.
- (From end of v1 sweep) `feat(strategy): add signal() advisory single-bar API` — closed spec §8 acceptance criterion 2 (single-bar live-use API). Commit `990e057`.

### Open issues deferred to a later sprint
- Real bias-window annotation by Simon — the 3 rows in `data/bias_windows.csv` are still `PLACEHOLDER`. Until they are replaced with real annotations, backtest output is illustrative, not decisional.
- `vol_span = 25` magic literal in `EWMAC.compute()` should be a constructor parameter.
- `BiasWindowLoader` `str(NaN)` → `'NaT'` for empty `note` cells (defensive, currently not hit because all 3 rows have notes).
- `pyproject.toml` `target-version = "py312"` vs `requires-python = ">=3.11"` minor inconsistency.
- AlphaForge benchmark via `compute_bh_equity` requires `bar_data._datetime` to be `datetime64[ns]`; demo currently passes that, but a more portable spec would be useful when other instruments are added.
- `conftest.py` shared fixtures (`synthetic_daily`, `synthetic_h1`) are defined but no test imports them — tests build their own helpers. Either consolidate or remove.

### Post-V11.1 AlphaForge K-line upgrade (consumer-side change, 2026-05-11)
QTrend_v2 was the **demand driver** for AlphaForge's K-line migration from Plotly candlesticks to **TradingView Lightweight Charts v5.2.0** (Apache-2.0, vendored). Side benefit for our reports:
- Authentic TradingView candlestick look with right-anchored price scale.
- Real time-axis gaps (weekends, holidays, lunch) instead of category-axis collapse.
- Native trade markers via `markers.aboveBar` / `belowBar` API; richer hover (price + lots + reason).
- Volume + indicator subplots synchronized to one crosshair.
- All 10+ other report sections (equity, drawdown, monthly heatmap, trade table, etc.) continue using Plotly. Both libraries coexist in the same HTML.

QTrend_v2 itself didn't change for this upgrade — we still consume `HTMLReportGenerator.generate()` exactly as before. The change is internal to AlphaForge on branch `feature/kline-tv-lightweight-charts` off `0b897f9`. Commit on our side: `4b26dc3`.

---

## v1.0 — initial implementation (shipped 2026-05-11)

15 tasks executed via `subagent-driven-development`. Two-stage review (spec compliance + code quality) per task. 22 commits, 50 tests, ~1325 source LOC.

### What shipped
- `qtrend_v2.types` — `Action / ActionKind / Leg / Fill` value objects.
- `qtrend_v2.data` — HC daily + 1H parquet loaders with optional date filter.
- `qtrend_v2.bias` — `BiasWindow / BiasWindowLoader` CSV parser + `data/bias_windows.csv` template (3 PLACEHOLDER rows).
- `qtrend_v2.forecast` — `ForecastSignal` ABC + `EWMAC(16, 64)` long-only clipped to [0, +20] via Carver's scalar.
- `qtrend_v2.sizing` — `Sizer` with bucketed thresholding 0-5 lots + 1-unit hysteresis deadband.
- `qtrend_v2.pullback.connors` — stateful Connors RSI(2) modulator on 1H; offset ∈ {-1, 0} so reload never pushes net above forecast-supported target.
- `qtrend_v2.state_machine` — legs + aggregate 3×ATR trailing stop (per-round reset) + 1H entry/exit timing filter (defer up to K=6 bars then force at market).
- `qtrend_v2.execution.simulator` — fill at next 1H bar open + fixed cost per lot.
- `qtrend_v2.backtest.run_window` — driver loop with daily ATR + 1H RSI compute, cash accounting, end-of-window force-flat.
- `qtrend_v2.strategy.Strategy` — top-level wiring with EWMAC + Connors + StateMachine defaults; two operating modes: `run_window()` (backtest) and `signal()` (live-use single-bar advisory).
- `qtrend_v2.report` — in-house per-window + aggregate HTML report (deprecated in v1.1 favour of `report_af`, but kept for `alphaforge`-less use).
- `notebooks/2026-05-11-v1-walkthrough.ipynb` — load HC → run window → render reports end-to-end demo.
- End-to-end smoke test on real HC parquet passes the 3 placeholder windows without error.

### Key v1 architecture decisions (recap from spec §11)
- Long-only single instrument (HC).
- Human bias from manual annotation; medium autonomy (engine may stay flat or exit early).
- Two timeframes: daily for trend + sizing, 1H for execution timing (weekly dropped because bias gate already plays the macro filter role).
- Carver-style continuous forecast → integer-lot sizing (Simon's explicit choice over Donchian-only breakout).
- Connors RSI(2) 1H pullback modulator (revised from initial ATR-distance proposal).
- Aggregate ATR trailing stop as sole hard exit (no drawdown gate, no time limit).
- Standalone repo with alphaforge as a dep — confirmed in v1.1.

---

## v0.1 — skeleton (2026-05-11)
Empty package + git init + this CHANGELOG's grandparent.
