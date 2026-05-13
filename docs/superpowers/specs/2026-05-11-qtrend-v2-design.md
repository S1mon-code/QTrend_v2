# QTrend_v2 — Design Spec

- **Date**: 2026-05-11
- **Author**: Simon + Claude (brainstorming session)
- **Status**: v1 shipped 2026-05-11; v1.1 (AlphaForge report integration) shipped 2026-05-11. See [docs/CHANGELOG.md](../../CHANGELOG.md) for what changed since this spec was written.
- **Repo**: `~/Desktop/QTrend_v2/` · [github.com/S1mon-code/QTrend_v2](https://github.com/S1mon-code/QTrend_v2)
- **Related research**: [`../../research/2026-05-11-indicator-frequency-research.md`](../../research/2026-05-11-indicator-frequency-research.md)
- **Implementation plan** (executed): [`../plans/2026-05-11-qtrend-v2-implementation.md`](../plans/2026-05-11-qtrend-v2-implementation.md)

> **Note on spec drift**: This document is preserved as the original design intent. Two areas have moved on:
> 1. §7 (Project layout) — `src/qtrend_v2/report_af.py` was added in v1.1 to bridge to AlphaForge.
> 2. §3 wording "Data loaders may be reused from `alphaforge.data`" was extended in v1.1 to include report rendering via `alphaforge.report.HTMLReportGenerator`.
> Detailed decisions are in the CHANGELOG; this spec is not edited beyond this note.

---

## 1. Purpose

A **long-only trend-capture engine** for Chinese commodity futures, single-instrument MVP on **HC (热卷)**. The engine is enabled by Simon's discretionary fundamental view (a `long bias` switch). When enabled, the engine autonomously sizes (0-5 lots), enters, manages, and exits positions to ride the trend during the bias window. The engine does **not** decide market direction — that is Simon's responsibility.

Future evolution path (out of scope for v1):
- Add quantitative fundamental signal as a second `bias` source
- Generalize to other Chinese commodity futures
- Wire to live execution (CTP / PythonGO)

---

## 2. Operating semantics

### 2.1 Bias gate (human in the loop)
- Bias is **binary**: `on` (long allowed) or `off` (forced flat).
- Bias source v1: Simon's manual annotation of historical windows for backtest; in live, Simon toggles externally.
- **Enable semantics**: "long allowed", **not** "long required". The engine may stay flat if its signal disagrees.
- **Disable semantics**: immediate forced flat. No grace period, no "soft disable".

### 2.2 Position state
- Position size is **integer lots in {0, 1, 2, 3, 4, 5}**.
- Active inventory management is allowed: scale up, scale down, trim before pullback, reload after.
- All legs are long-only.

### 2.3 Holding period
- Minimum: ~1 week (no formal lower bound; trailing stop may exit faster).
- Maximum: 1 quarter (no hard timer; bias window typically closes first).
- Median target: ~1 month.

### 2.4 Exit triggers (priority order, highest first)
1. **Bias `off`** → force flat all lots
2. **ATR trailing stop hit** → force flat all lots (priced trailing stop, see §5)
3. **Forecast decay** → soft scale-down via target_lots derivative

### 2.5 Autonomy boundary
- Engine **may** refuse to enter (target_lots = 0) even when bias = on.
- Engine **may** exit fully via trailing stop before bias = off.
- Engine **may not** go short, ever.

---

## 3. Data architecture

### 3.1 Sources (reused from existing infrastructure)
| Path | Use |
|---|---|
| `~/Desktop/data/CN/market/continuous/HC9999.parquet` | daily bars on continuous contract |
| `~/Desktop/data/CN/market/continuous/.cache/HC_60min.parquet` | 1H bars |
| `~/Desktop/data/CN/market/continuous/.cache/HC_daily.parquet` | daily bars (alt source) |
| `~/Desktop/data/CN/market/roll_engine/output/roll_calendar_HC.csv` | contract roll calendar |

Data loaders may be reused from `alphaforge.data`.

### 3.2 Timeframes
| Layer | Frequency | Role |
|---|---|---|
| Macro | Bias gate (event-driven) | Replaces weekly trend filter; comes from Simon |
| Trend | Daily | Forecast computation, target_lots, ATR trailing stop level |
| Execution | 1H | Entry/exit timing, pullback modulator (Connors RSI(2) / BB%B) |

### 3.3 Roll handling
Use the existing roll calendar. The strategy operates on the **continuous price** (back-adjusted) for signal computation; legs are sized on continuous contract (treated as one synthetic instrument). Document any cross-contract assumptions in `qtrend_v2.data`.

---

## 4. Strategy architecture (Carver-style continuous forecast)

```
                Simon's bias (manual / external)
                          │
                       on │ off
                          ▼
   ┌─────────────────────────────────────────┐
   │ Daily bars                              │
   │   │                                     │
   │   ▼                                     │
   │ ForecastSignal (long-only [0, +20])     │  ←─ swappable: EWMAC / TSMOM /
   │   │                                     │       Donchian-fraction / etc.
   │   ▼                                     │
   │ Sizing  (forecast → target_lots ∈ 0..5) │
   │   │       with hysteresis to avoid       │
   │   ▼       flickering between buckets    │
   └─────────────────────────────────────────┘
                          │  target_lots (daily-updated)
                          ▼
   ┌─────────────────────────────────────────┐
   │ 1H bars                                 │
   │   │                                     │
   │   ▼                                     │
   │ PullbackModulator  (Connors-style)      │  ─→ stateful offset ∈ {-1, 0}
   │   │  RSI(2) > 95 ⇒ trim (offset → -1)   │     applied to target_lots
   │   │  RSI(2) < 10 ⇒ reload (offset → 0)  │  (reload only undoes a prior trim;
   │   │  Gated by forecast strength         │   never pushes net above forecast)
   │   ▼                                     │
   │ StateMachine                            │
   │   ├─ Current legs (price, lots, stop)   │
   │   ├─ ATR trailing stop (3×ATR daily)    │
   │   ├─ 1H entry/exit timing (action timing)│
   │   └─ Emits: BUY n / SELL n / HOLD       │
   └─────────────────────────────────────────┘
                          │
                          ▼
                 ExecutionAdapter
                 (v1: sim matching;
                  later: PythonGO/CTP)
```

### 4.1 ForecastSignal (plug-in interface)

```python
class ForecastSignal(ABC):
    @abstractmethod
    def compute(self, daily_bars: pd.DataFrame) -> pd.Series:
        """Return forecast in [0, +20] indexed by daily date.
        Long-only: negative values are clipped to 0."""
```

v1 default: **EWMAC(16, 64)** — Carver's medium-term span, vol-normalized, clipped to [0, +20].
Alternates shipped as swappable implementations: `TSMOM` (1M+3M momentum sign), `DonchianFraction` (continuous version of breakout).

**Note**: The final choice of forecast for live use is **explicitly deferred** post-v1. v1 ships with EWMAC as a working placeholder; backtest results across multiple forecasts will inform the choice.

### 4.2 Sizing (forecast → integer lots)

Bucketed thresholding with **hysteresis** (deadband) to prevent flickering:

| Forecast | Target lots (rising) | Target lots (falling) |
|---|---|---|
| 0 – 4 | 0 | 0 |
| 4 – 8 | 1 | requires ≤ 3 to drop to 0 |
| 8 – 12 | 2 | requires ≤ 7 to drop to 1 |
| 12 – 16 | 3 | requires ≤ 11 to drop to 2 |
| 16 – 20 | 4 | requires ≤ 15 to drop to 3 |
| 20+ (saturate at 20) | 5 | requires ≤ 19 to drop to 4 |

Hysteresis band is 1 forecast unit. Tuned during v1 validation.

### 4.3 PullbackModulator (Connors-style on 1H)

The modulator is **stateful**. It maintains an internal `offset ∈ {-1, 0}` and applies that offset to the daily `target_lots`. The reload signal only undoes a prior trim — it never pushes the net target above what the daily forecast supports.

```python
class PullbackModulator:
    def __init__(self, forecast_min: float = 8.0):
        self._offset: int = 0  # in {-1, 0}; reset on bias-window start

    def adjust(self, h1_bars: pd.DataFrame, current_forecast: float,
               current_target: int) -> int:
        """Return adjusted target_lots ∈ [0, current_target].
        Stateful: offset transitions on 1H signals.
        Gated: no-op when current_forecast < forecast_min."""

    def reset(self) -> None:
        """Reset offset to 0; called at start of each bias window."""
```

Transition rules on each 1H bar:
- `RSI(2) > 95` and `offset == 0`  → `offset := -1` (trim — overbought, expect pullback)
- `RSI(2) < 10` and `offset == -1` → `offset := 0`  (reload — pullback complete)
- Otherwise → offset unchanged

Final returned target: `clip(current_target + offset, 0, current_target)` — note the upper bound is `current_target`, not 5; this enforces that the modulator can only subtract from, not add beyond, the daily forecast-derived target.

**Gating**: modulator is **inactive** (offset stays 0) when forecast < `forecast_min` (default 8, i.e., target ≤ 1). At very low forecast there is no headroom to meaningfully trim/reload.

**Optional confirmation**: BB %B > 0.95 / < 0.05 as a redundant signal (ensemble AND or majority vote). v1 ships RSI(2) only; BB%B reserved as a follow-up experiment.

### 4.4 StateMachine (legs, stop, action emission)

Responsibilities:
- Track open legs with entry price, lot count.
- Maintain a **single aggregate ATR trailing stop**: `stop = max(daily_close_since_round_start) - 3×ATR(20)`.
  - **"Round" semantics**: a round begins on the first entry after `current_lots == 0` and ends when the position next returns to 0 (via stop hit, bias off, or forecast→0). On round end, the trailing reference is **reset**. A new round inside the same bias window therefore has its own trailing stop, independent of the previous round's peak.
- On every 1H bar:
  1. If `price ≤ stop` and `current_lots > 0` → emit `FLAT_ALL` (close round, reset trailing reference).
  2. Else if `current_lots != target_lots_after_modulator`:
     - Decide `BUY n` or `SELL n` (n = absolute diff).
     - **Entry/scale-up timing**: prefer 1H bars closing with `RSI(2) < 50` (avoid chasing).
     - **Exit/scale-down timing**: prefer 1H bars closing with `RSI(2) ≥ 50` (don't dump into oversold).
     - If timing constraint not met within `K_1h_bars = 6` (i.e., ~6 hours), execute at market on the next 1H open.
- On `bias = off` event: emit `FLAT_ALL` immediately, close round.

### 4.5 ExecutionAdapter (v1: simulator)

v1 ships only a **simulator adapter** that:
- Fills at the next 1H bar's open (no intra-bar fills).
- Applies a fixed transaction cost: 1 tick + 0.0001 of notional (configurable).
- Logs every action with timestamp, price, reason, resulting state.

---

## 5. Bias window mechanism (backtest)

### 5.1 File format
`~/Desktop/QTrend_v2/data/bias_windows.csv`:

```csv
start_date,end_date,note
2023-03-15,2023-05-20,"low inventory + construction season"
2024-01-08,2024-04-10,"special bond front-loading + property easing"
```

- Each row = one closed-interval long bias window.
- `note` column is mandatory (forces Simon to record the fundamental thesis).
- File is **version-controlled and committed before the backtest is run** — establishes an audit trail and prevents look-ahead bias from post-hoc edits.

### 5.2 Loader API
```python
class BiasWindowLoader:
    def __init__(self, csv_path: str): ...
    def is_bias_on(self, dt: pd.Timestamp) -> bool: ...
    def windows(self) -> list[BiasWindow]: ...

@dataclass(frozen=True)
class BiasWindow:
    start: pd.Timestamp
    end: pd.Timestamp
    note: str
```

### 5.3 Backtest semantics
- Outside any window: `target_lots ≡ 0`, no positions opened.
- On window `end` date: force flat (regardless of forecast / stop state).
- Per-window state is independent: the state machine is **reset** at the start of each window (no carry-over legs).

---

## 6. Backtest driver and reporting

### 6.1 Driver loop
```python
for window in bias_loader.windows():
    state_machine.reset()
    daily = load_daily(start=window.start, end=window.end)
    h1    = load_1h(start=window.start, end=window.end)
    forecast = forecast_signal.compute(daily)
    for ts_h1 in h1.index:
        bar_daily = daily.loc[:ts_h1.date()].iloc[-1]
        current_forecast = forecast.loc[bar_daily.name]
        target = sizing.compute(current_forecast)
        modulated_target = pullback.adjust(h1.loc[:ts_h1], current_forecast, target)
        state_machine.step(ts_h1, h1.loc[ts_h1], target=modulated_target)
    state_machine.force_flat(reason='bias_off')
    record_window_result(window, state_machine.history())
```

### 6.2 Per-window report (HTML)
- Price chart with lot-count overlay (step plot).
- Daily forecast time series + sizing buckets shaded.
- Decision log: every BUY / SELL / FLAT / STOP_HIT with timestamp, price, reason.
- Cumulative PnL + drawdown.
- 1H modulator activity log (trim/reload events).

### 6.3 Aggregate report
- PnL distribution across windows (box plot + histogram).
- Hit rate (% of windows with positive PnL).
- Worst-window drawdown.
- Distribution of time-in-market (lot-day-fraction).
- Per-window Sharpe distribution.
- Modulator contribution analysis: PnL with vs without pullback modulator (controlled re-run).

Render via `alphaforge.report` HTML scaffold.

---

## 7. Project layout

```
~/Desktop/QTrend_v2/
├── pyproject.toml                # standalone package; deps: alphaforge, pandas, numpy, scipy
├── README.md
├── .gitignore
├── src/qtrend_v2/
│   ├── __init__.py
│   ├── strategy.py               # top-level entry: Strategy(...) class
│   ├── data.py                   # data loaders (wrap alphaforge.data)
│   ├── bias.py                   # BiasWindowLoader, BiasWindow
│   ├── forecast/
│   │   ├── __init__.py
│   │   ├── base.py               # ForecastSignal ABC
│   │   ├── ewmac.py              # default v1
│   │   ├── tsmom.py              # alternate
│   │   └── donchian_frac.py      # alternate
│   ├── pullback/
│   │   ├── __init__.py
│   │   └── connors.py            # RSI(2) / BB%B modulator (1H)
│   ├── sizing.py                 # forecast → integer lots + hysteresis
│   ├── state_machine.py          # legs, ATR trailing stop, action emitter, 1H timing
│   ├── execution/
│   │   ├── __init__.py
│   │   └── simulator.py          # v1 execution adapter
│   ├── backtest.py               # driver over bias windows
│   └── report.py                 # per-window + aggregate report (uses alphaforge.report)
├── notebooks/
│   ├── 2026-05-11-v1-walkthrough.ipynb
│   └── README.md
├── data/
│   └── bias_windows.csv          # Simon's manual annotations (sample/template)
├── tests/
│   ├── test_bias.py
│   ├── test_sizing.py
│   ├── test_pullback.py
│   ├── test_state_machine.py
│   └── test_backtest_smoke.py
├── reports/                      # generated reports (gitignored)
└── docs/
    ├── superpowers/specs/
    │   └── 2026-05-11-qtrend-v2-design.md   (this file)
    └── research/
        └── 2026-05-11-indicator-frequency-research.md
```

---

## 8. v1 acceptance criteria

Acceptance = **all** of the following:

- [ ] `from qtrend_v2 import Strategy; s = Strategy(forecast=EWMAC(), pullback=Connors())` — callable, no errors.
- [ ] `s.signal(daily_bars, h1_bars, current_lots) -> ActionPlan` — returns deterministic action given inputs.
- [ ] `BiasWindowLoader('data/bias_windows.csv')` correctly parses ≥ 3 sample windows.
- [ ] `backtest.run(strategy=s, bias=loader, daily=..., h1=...)` runs over all sample windows without error.
- [ ] Per-window HTML report renders correctly for each sample window.
- [ ] Aggregate report includes: hit rate, total PnL, PnL distribution, worst-window DD, time-in-market distribution.
- [ ] Unit tests pass for: `bias`, `sizing` (including hysteresis), `pullback` (gating), `state_machine` (trailing stop, leg accounting).
- [ ] Smoke test backtest passes on a deterministic synthetic window (golden numbers).
- [ ] One notebook walks end-to-end through a single window with narration.
- [ ] All tests live; `ruff format` and `ruff check` clean.

---

## 9. Out of scope for v1

- Live execution adapter (CTP / PythonGO / openctp)
- Paper trading driver
- Quantitative fundamental bias proxy (manual annotation only)
- Multi-instrument generalization (HC only)
- Parameter optimization / sweep
- Final forecast selection (v1 ships EWMAC as placeholder; selection deferred)
- Cross-product or term-structure signals
- Trade attribution / per-leg PnL accounting (aggregate PnL only)
- Margin / position-size in capital units (lots only)

---

## 10. Open questions deferred to writing-plans phase

These are deliberately left for the plan-writing stage, not for further design discussion:

1. **Forecast selection methodology**: how to compare EWMAC / TSMOM / Donchian-fraction on the bias windows once the harness is up. (Likely a separate workstream in v1 or v1.1.)
2. **ATR trailing stop variants**: 3×ATR(20) is the v1 default. Per-leg vs aggregate (we chose aggregate) is settled, but the coefficient and the ATR lookback are tunable.
3. **1H timing thresholds**: `RSI(2) > 95` / `< 10` and `< 50` / `> 50` are starting points from research; will be sanity-checked on HC 1H bars before v1 ships.
4. **Bias window historical annotation effort**: Simon will need to produce ≥ 3 annotated windows; the exact set and the methodology (e.g., write windows before looking at HC chart performance, to avoid look-ahead) is a Simon-side workstream.
5. **AlphaForge integration surface**: which exact alphaforge modules to import (`alphaforge.engine`, `alphaforge.report`, `alphaforge.indicators`, `alphaforge.data`). To be resolved when scaffolding starts.

---

## 11. Decision audit

Decisions recorded in this brainstorming session (each one a tradeoff):

| # | Decision | Alternative considered | Rationale |
|---|---|---|---|
| 1 | Long-only, single instrument (HC) | Multi-instrument, long/short | Match Simon's fundamental view methodology; minimal v1 scope. |
| 2 | Bias from human (manual annotation) | Quantitative proxy (MA slope, fundamental score) | Most realistic for live use; sample size cost is accepted. |
| 3 | Medium autonomy (engine may stay flat / exit early) | Strong subordination (always long when bias on) | Allow engine to save Simon from a wrong call. |
| 4 | Daily + 1H two timeframes | Weekly + daily + 1H three TFs | Bias gate replaces weekly role; deep research §2 supported simplification. |
| 5 | Carver-style continuous forecast → integer lots | Donchian breakout discrete (Approach C in brainstorm) | Simon's explicit choice; cleaner active mgmt; signal layer swappable. |
| 6 | Connors-style 1H RSI(2) / BB%B pullback modulator | Daily ATR-distance-from-MA | Simon's revision; uses 1H data more directly; faster reactivity. |
| 7 | 3×ATR aggregate trailing stop (sole hard exit) | Drawdown gate / time limit / signal exit | Simon chose price-driven exit only; simpler and predictable. |
| 8 | Standalone repo importing alphaforge | Subdir of alphaforge | Decoupling; QTrend_v2 evolves on its own cadence. |
| 9 | v1 scope: callable strategy + multi-window backtest + reports | + paper trade / + live | Earlier scope cuts; live deferred until strategy is validated. |
| 10 | EWMAC(16, 64) as default forecast for v1 | TSMOM / Donchian-fraction | Research recommendation; alternatives shipped as plug-ins for later comparison. |

---

## 12. Glossary

- **Bias**: Simon's discretionary long signal. Binary on/off. Not derived by the engine.
- **Forecast**: Continuous trend strength signal computed by the engine, scaled to [0, +20] (long-only).
- **Target lots**: Integer position size in {0..5} derived from forecast via sizing buckets.
- **Pullback modulator**: 1H signal that adjusts target_lots by ±1 to capture short-term overbought / oversold.
- **ATR trailing stop**: Price-based exit at `highest_close_since_first_entry - 3×ATR(20)`, applied to aggregate position.
- **Bias window**: Closed-interval `[start, end]` during which `is_bias_on` is True for the backtest.
- **Leg**: A single entry transaction (price, size). The state machine tracks legs but applies aggregate trailing stop.
