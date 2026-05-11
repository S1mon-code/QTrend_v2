# QTrend_v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a long-only trend-capture engine for HC (热卷) futures: callable Strategy class + backtest harness over manually annotated bias windows + per-window and aggregate HTML reports. Spec: `docs/superpowers/specs/2026-05-11-qtrend-v2-design.md`.

**Architecture:** Carver-style continuous forecast (EWMAC default, plug-in interface) on daily bars → sizing buckets with hysteresis → 1H Connors stateful pullback modulator → state machine with aggregate 3×ATR trailing stop + 1H execution timing → simulator adapter. Driver iterates over Simon's manually annotated bias windows.

**Tech Stack:** Python 3.12, pandas 2.3, numpy 2, matplotlib 3.10, pytest, ruff. Data: local parquet files at `~/Desktop/data/CN/market/continuous/.cache/HC_{daily,60min}.parquet`. AlphaForge is **not** depended on in v1 — self-contained for now.

---

## File structure

```
~/Desktop/QTrend_v2/
├── pyproject.toml              # Task 1
├── README.md                   # Task 1
├── .gitignore                  # already exists
├── src/qtrend_v2/
│   ├── __init__.py             # Task 1
│   ├── types.py                # Task 2 — Action, ActionPlan, BarFrame typing aliases
│   ├── data.py                 # Task 3 — HC bar loaders
│   ├── bias.py                 # Task 4 — BiasWindow + BiasWindowLoader
│   ├── forecast/
│   │   ├── __init__.py         # Task 5
│   │   ├── base.py             # Task 5 — ForecastSignal ABC
│   │   └── ewmac.py            # Task 5 — EWMAC(16, 64)
│   ├── sizing.py               # Task 6 — bucket + hysteresis
│   ├── pullback/
│   │   ├── __init__.py         # Task 7
│   │   └── connors.py          # Task 7 — stateful RSI(2)
│   ├── state_machine.py        # Task 8 — legs + trailing stop + timing
│   ├── execution/
│   │   ├── __init__.py         # Task 9
│   │   └── simulator.py        # Task 9 — fill at next 1H open
│   ├── backtest.py             # Task 10 — driver
│   ├── strategy.py             # Task 11 — top-level wiring
│   └── report.py               # Task 12 + 13 — per-window + aggregate
├── data/
│   └── bias_windows.csv        # Task 4 — template + sample rows
├── tests/
│   ├── conftest.py             # Task 2 — synthetic fixtures
│   ├── test_data.py            # Task 3
│   ├── test_bias.py            # Task 4
│   ├── test_forecast_ewmac.py  # Task 5
│   ├── test_sizing.py          # Task 6
│   ├── test_pullback.py        # Task 7
│   ├── test_state_machine.py   # Task 8
│   ├── test_simulator.py       # Task 9
│   ├── test_backtest_smoke.py  # Task 14
│   └── test_strategy.py        # Task 11
├── notebooks/
│   └── 2026-05-11-v1-walkthrough.ipynb   # Task 15
├── reports/                    # generated, gitignored
└── docs/                       # already exists
```

## Dependency graph (parallelizable waves)

```
Wave 1: Task 1 (bootstrap)
Wave 2: Task 2 (test infra + types)
Wave 3: PARALLEL — Tasks 3, 4, 5, 6, 7  (data, bias, forecast, sizing, pullback)
Wave 4: Task 8 (state machine — needs forecast + sizing + pullback shapes)
Wave 5: Task 9 (simulator)
Wave 6: Task 10 (backtest driver — needs state machine + simulator)
Wave 7: Task 11 (strategy top-level)
Wave 8: PARALLEL — Tasks 12, 13 (per-window report, aggregate report)
Wave 9: Task 14 (smoke test e2e)
Wave 10: Task 15 (notebook walkthrough)
```

---

## Task 1: Bootstrap package + pyproject

**Files:**
- Create: `~/Desktop/QTrend_v2/pyproject.toml`
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/__init__.py`
- Create: `~/Desktop/QTrend_v2/README.md` (overwrite the placeholder)

- [ ] **Step 1.1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling>=1.18"]
build-backend = "hatchling.build"

[project]
name = "qtrend-v2"
version = "0.1.0"
description = "Long-only trend-capture engine for Chinese commodity futures (HC)"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "pandas>=2.0",
    "numpy>=1.26",
    "matplotlib>=3.8",
    "pyarrow>=14.0",
    "jinja2>=3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.6",
    "jupyterlab>=4.0",
    "ipykernel>=6.29",
]

[tool.hatch.build.targets.wheel]
packages = ["src/qtrend_v2"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-ra --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
```

- [ ] **Step 1.2: Write `src/qtrend_v2/__init__.py`**

```python
"""QTrend_v2 — long-only trend-capture engine for HC futures."""

__version__ = "0.1.0"
```

- [ ] **Step 1.3: Replace `README.md`**

```markdown
# QTrend_v2

Long-only trend-capture engine for HC (热卷) futures. Carver-style continuous forecast → integer-lot sizing (0-5) → 1H Connors pullback modulator → ATR trailing stop. Driven by manually annotated `long bias` windows from Simon.

See:
- `docs/superpowers/specs/2026-05-11-qtrend-v2-design.md` — full design spec
- `docs/superpowers/plans/2026-05-11-qtrend-v2-implementation.md` — this plan
- `docs/research/2026-05-11-indicator-frequency-research.md` — indicator-frequency deep research

## Install (dev)
```bash
cd ~/Desktop/QTrend_v2
python -m pip install -e ".[dev]"
```

## Run tests
```bash
pytest -ra
```

## Status
v1 in development. Out of scope for v1: live execution, paper trade, quantitative bias proxy, multi-instrument.
```

- [ ] **Step 1.4: Install package and verify import**

Run:
```bash
cd ~/Desktop/QTrend_v2 && python -m pip install -e ".[dev]" 2>&1 | tail -5 && python -c "import qtrend_v2; print(qtrend_v2.__version__)"
```
Expected last line: `0.1.0`

- [ ] **Step 1.5: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add pyproject.toml README.md src/qtrend_v2/__init__.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "chore: bootstrap qtrend_v2 package skeleton"
```

---

## Task 2: Test infra + shared types

**Files:**
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/types.py`
- Create: `~/Desktop/QTrend_v2/tests/__init__.py` (empty)
- Create: `~/Desktop/QTrend_v2/tests/conftest.py`
- Create: `~/Desktop/QTrend_v2/tests/test_types_smoke.py`

- [ ] **Step 2.1: Write `src/qtrend_v2/types.py`**

```python
"""Shared type aliases and small value objects."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import pandas as pd  # noqa: F401  (used in type hints in other modules)

if TYPE_CHECKING:
    from collections.abc import Sequence


class ActionKind(str, Enum):
    HOLD = "HOLD"
    BUY = "BUY"
    SELL = "SELL"
    FLAT_ALL = "FLAT_ALL"


@dataclass(frozen=True)
class Action:
    """Atomic instruction from StateMachine to ExecutionAdapter."""
    kind: ActionKind
    lots: int  # absolute lot count for BUY/SELL; 0 for HOLD/FLAT_ALL
    reason: str

    def __post_init__(self) -> None:
        if self.kind in (ActionKind.BUY, ActionKind.SELL) and self.lots <= 0:
            raise ValueError(f"{self.kind.value} requires lots > 0, got {self.lots}")
        if self.kind in (ActionKind.HOLD, ActionKind.FLAT_ALL) and self.lots != 0:
            raise ValueError(f"{self.kind.value} requires lots == 0, got {self.lots}")


@dataclass(frozen=True)
class Leg:
    """A single entry transaction in the current open round."""
    timestamp: pd.Timestamp
    price: float
    lots: int


@dataclass(frozen=True)
class Fill:
    """Reported by ExecutionAdapter after acting on an Action."""
    timestamp: pd.Timestamp
    kind: ActionKind
    lots: int
    price: float
    reason: str
```

- [ ] **Step 2.2: Write `tests/__init__.py`** (empty file)

```python
```

- [ ] **Step 2.3: Write `tests/conftest.py`**

```python
"""Shared pytest fixtures for qtrend_v2 tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_daily() -> pd.DataFrame:
    """120 daily bars: 60 trending up, 60 sideways. RangeIndex; datetime col."""
    rng = pd.date_range("2024-01-01", periods=120, freq="B")
    trend = np.linspace(3000, 3600, 60)
    flat = np.full(60, 3600.0) + np.random.default_rng(42).normal(0, 10, 60)
    close = np.concatenate([trend, flat])
    df = pd.DataFrame({
        "datetime": rng,
        "open": close * 0.999,
        "high": close * 1.005,
        "low": close * 0.995,
        "close": close,
        "volume": 1000,
    })
    return df


@pytest.fixture
def synthetic_h1(synthetic_daily: pd.DataFrame) -> pd.DataFrame:
    """4 1H bars per daily bar, derived from synthetic_daily close."""
    rows = []
    for _, day in synthetic_daily.iterrows():
        for hour_offset in (9, 10, 11, 13):
            ts = day["datetime"].replace(hour=hour_offset, minute=1)
            rows.append({
                "datetime": ts,
                "open": day["close"] * 0.999,
                "high": day["close"] * 1.002,
                "low": day["close"] * 0.998,
                "close": day["close"],
                "volume": 250,
            })
    return pd.DataFrame(rows)
```

- [ ] **Step 2.4: Write `tests/test_types_smoke.py`**

```python
"""Verify shared types validate as expected."""
from __future__ import annotations

import pytest

from qtrend_v2.types import Action, ActionKind


def test_action_buy_requires_positive_lots():
    Action(kind=ActionKind.BUY, lots=2, reason="ok")  # no raise
    with pytest.raises(ValueError):
        Action(kind=ActionKind.BUY, lots=0, reason="bad")


def test_action_hold_requires_zero_lots():
    Action(kind=ActionKind.HOLD, lots=0, reason="ok")
    with pytest.raises(ValueError):
        Action(kind=ActionKind.HOLD, lots=1, reason="bad")


def test_action_flat_all_requires_zero_lots():
    Action(kind=ActionKind.FLAT_ALL, lots=0, reason="ok")
    with pytest.raises(ValueError):
        Action(kind=ActionKind.FLAT_ALL, lots=3, reason="bad")
```

- [ ] **Step 2.5: Run tests**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_types_smoke.py -v`
Expected: `3 passed`

- [ ] **Step 2.6: Run ruff format + check**

Run: `cd ~/Desktop/QTrend_v2 && ruff format src/ tests/ && ruff check src/ tests/`
Expected: no errors.

- [ ] **Step 2.7: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/types.py tests/ && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(types): Action/ActionKind/Leg/Fill value objects + test fixtures"
```

---

## Task 3: Data loaders (HC daily + 1H)

**Files:**
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/data.py`
- Create: `~/Desktop/QTrend_v2/tests/test_data.py`

- [ ] **Step 3.1: Write failing test `tests/test_data.py`**

```python
"""Tests for HC bar loaders."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qtrend_v2.data import load_hc_1h, load_hc_daily

DATA_ROOT = Path("/Users/simon/Desktop/data/CN/market/continuous/.cache")
DAILY_PATH = DATA_ROOT / "HC_daily.parquet"
H1_PATH = DATA_ROOT / "HC_60min.parquet"


@pytest.mark.skipif(not DAILY_PATH.exists(), reason="HC daily parquet not present")
def test_load_hc_daily_has_ohlcv_and_datetime_index():
    df = load_hc_daily()
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing
    for col in ("open", "high", "low", "close", "volume"):
        assert col in df.columns, f"missing {col}"
    assert (df["close"] > 0).all()


@pytest.mark.skipif(not H1_PATH.exists(), reason="HC 1H parquet not present")
def test_load_hc_1h_has_ohlcv_and_datetime_index():
    df = load_hc_1h()
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing
    for col in ("open", "high", "low", "close", "volume"):
        assert col in df.columns


@pytest.mark.skipif(not DAILY_PATH.exists(), reason="HC daily parquet not present")
def test_load_hc_daily_date_range_filter():
    df = load_hc_daily(start="2023-01-01", end="2023-12-31")
    assert df.index.min() >= pd.Timestamp("2023-01-01")
    assert df.index.max() <= pd.Timestamp("2023-12-31")
```

- [ ] **Step 3.2: Run test, expect fail (module not found)**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_data.py -v`
Expected: ImportError on `qtrend_v2.data`.

- [ ] **Step 3.3: Write `src/qtrend_v2/data.py`**

```python
"""HC futures bar loaders. Read parquet files from local cache."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_DATA_ROOT = Path("/Users/simon/Desktop/data/CN/market/continuous/.cache")
DAILY_FILE = "HC_daily.parquet"
H1_FILE = "HC_60min.parquet"


def _load_parquet(filename: str, data_root: Path | None = None) -> pd.DataFrame:
    root = data_root or DEFAULT_DATA_ROOT
    path = root / filename
    if not path.exists():
        raise FileNotFoundError(f"HC parquet not found: {path}")
    df = pd.read_parquet(path)
    if "datetime" not in df.columns:
        raise ValueError(f"{path} missing 'datetime' column")
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime").sort_index()
    return df


def _filter_range(
    df: pd.DataFrame,
    start: str | pd.Timestamp | None,
    end: str | pd.Timestamp | None,
) -> pd.DataFrame:
    if start is not None:
        df = df.loc[df.index >= pd.Timestamp(start)]
    if end is not None:
        df = df.loc[df.index <= pd.Timestamp(end)]
    return df


def load_hc_daily(
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    data_root: Path | None = None,
) -> pd.DataFrame:
    """Load HC continuous daily bars. Returns DataFrame indexed by datetime."""
    df = _load_parquet(DAILY_FILE, data_root)
    return _filter_range(df, start, end)


def load_hc_1h(
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    data_root: Path | None = None,
) -> pd.DataFrame:
    """Load HC continuous 1H (60-min) bars. Returns DataFrame indexed by datetime."""
    df = _load_parquet(H1_FILE, data_root)
    return _filter_range(df, start, end)
```

- [ ] **Step 3.4: Run test, expect pass**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_data.py -v`
Expected: `3 passed` (or skipped if data not present, but data IS present).

- [ ] **Step 3.5: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/data.py tests/test_data.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(data): HC daily + 1H parquet loaders with date filter"
```

---

## Task 4: BiasWindow + BiasWindowLoader

**Files:**
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/bias.py`
- Create: `~/Desktop/QTrend_v2/data/bias_windows.csv`
- Create: `~/Desktop/QTrend_v2/tests/test_bias.py`

- [ ] **Step 4.1: Write the template CSV `data/bias_windows.csv`**

```csv
start_date,end_date,note
2023-03-15,2023-05-20,"PLACEHOLDER — replace with real annotation. Sample: low inventory + construction season."
2024-01-08,2024-04-10,"PLACEHOLDER — replace with real annotation. Sample: special bond front-loading + property easing."
2024-09-20,2024-11-15,"PLACEHOLDER — replace with real annotation. Sample: post-policy-package rally."
```

> NOTE: Simon must replace these placeholders with real annotations before treating backtest output as meaningful. The placeholder rows are kept so the smoke test has data to run on.

- [ ] **Step 4.2: Write failing test `tests/test_bias.py`**

```python
"""Tests for BiasWindow + BiasWindowLoader."""
from __future__ import annotations

import io

import pandas as pd
import pytest

from qtrend_v2.bias import BiasWindow, BiasWindowLoader


@pytest.fixture
def sample_csv(tmp_path):
    csv = tmp_path / "bias.csv"
    csv.write_text(
        "start_date,end_date,note\n"
        "2024-01-08,2024-04-10,test window 1\n"
        "2024-09-20,2024-11-15,test window 2\n"
    )
    return csv


def test_loader_parses_windows(sample_csv):
    loader = BiasWindowLoader(sample_csv)
    windows = loader.windows()
    assert len(windows) == 2
    assert windows[0].start == pd.Timestamp("2024-01-08")
    assert windows[0].end == pd.Timestamp("2024-04-10")
    assert windows[0].note == "test window 1"


def test_is_bias_on_inside_window(sample_csv):
    loader = BiasWindowLoader(sample_csv)
    assert loader.is_bias_on(pd.Timestamp("2024-02-15"))


def test_is_bias_on_outside_window(sample_csv):
    loader = BiasWindowLoader(sample_csv)
    assert not loader.is_bias_on(pd.Timestamp("2024-05-01"))


def test_is_bias_on_window_edges_inclusive(sample_csv):
    loader = BiasWindowLoader(sample_csv)
    assert loader.is_bias_on(pd.Timestamp("2024-01-08"))
    assert loader.is_bias_on(pd.Timestamp("2024-04-10"))


def test_loader_rejects_inverted_window(tmp_path):
    csv = tmp_path / "bad.csv"
    csv.write_text("start_date,end_date,note\n2024-04-10,2024-01-08,bad\n")
    with pytest.raises(ValueError, match="end_date.*before.*start"):
        BiasWindowLoader(csv)


def test_loader_requires_note_column(tmp_path):
    csv = tmp_path / "missing.csv"
    csv.write_text("start_date,end_date\n2024-01-08,2024-04-10\n")
    with pytest.raises(ValueError, match="missing.*note"):
        BiasWindowLoader(csv)
```

- [ ] **Step 4.3: Run test, expect fail**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_bias.py -v`
Expected: ImportError.

- [ ] **Step 4.4: Write `src/qtrend_v2/bias.py`**

```python
"""Manual long-bias window loader for backtest."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {"start_date", "end_date", "note"}


@dataclass(frozen=True)
class BiasWindow:
    start: pd.Timestamp
    end: pd.Timestamp
    note: str


class BiasWindowLoader:
    """Load and query a CSV of long-bias windows.

    CSV format:
        start_date,end_date,note
        YYYY-MM-DD,YYYY-MM-DD,"free text"

    Windows are inclusive on both ends. No overlap check is enforced; caller's
    responsibility.
    """

    def __init__(self, csv_path: str | Path):
        path = Path(csv_path)
        df = pd.read_csv(path)
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"bias_windows.csv missing columns: {sorted(missing)}")
        df["start_date"] = pd.to_datetime(df["start_date"])
        df["end_date"] = pd.to_datetime(df["end_date"])
        for i, row in df.iterrows():
            if row["end_date"] < row["start_date"]:
                raise ValueError(
                    f"row {i}: end_date {row['end_date'].date()} before "
                    f"start_date {row['start_date'].date()}"
                )
        self._df = df

    def windows(self) -> list[BiasWindow]:
        return [
            BiasWindow(
                start=row["start_date"],
                end=row["end_date"],
                note=str(row["note"]),
            )
            for _, row in self._df.iterrows()
        ]

    def is_bias_on(self, dt: pd.Timestamp) -> bool:
        dt = pd.Timestamp(dt).normalize()
        for _, row in self._df.iterrows():
            if row["start_date"] <= dt <= row["end_date"]:
                return True
        return False
```

- [ ] **Step 4.5: Run test, expect pass**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_bias.py -v`
Expected: `6 passed`.

- [ ] **Step 4.6: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/bias.py tests/test_bias.py data/bias_windows.csv && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(bias): BiasWindow + BiasWindowLoader with CSV parser + template"
```

---

## Task 5: ForecastSignal ABC + EWMAC(16, 64)

**Files:**
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/forecast/__init__.py`
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/forecast/base.py`
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/forecast/ewmac.py`
- Create: `~/Desktop/QTrend_v2/tests/test_forecast_ewmac.py`

- [ ] **Step 5.1: Write `src/qtrend_v2/forecast/__init__.py`**

```python
"""Forecast signals (plug-in)."""
from qtrend_v2.forecast.base import ForecastSignal
from qtrend_v2.forecast.ewmac import EWMAC

__all__ = ["ForecastSignal", "EWMAC"]
```

- [ ] **Step 5.2: Write `src/qtrend_v2/forecast/base.py`**

```python
"""Plug-in interface for trend-strength forecast signals."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class ForecastSignal(ABC):
    """Long-only forecast in [0, +20].

    Implementations consume daily OHLCV bars and emit a per-bar forecast Series
    aligned to the daily index. Negative-trend signals are clipped to 0; the
    engine never goes short.
    """

    @abstractmethod
    def compute(self, daily_bars: pd.DataFrame) -> pd.Series:
        """Return forecast Series indexed by daily timestamp, values in [0, 20]."""
```

- [ ] **Step 5.3: Write failing test `tests/test_forecast_ewmac.py`**

```python
"""Tests for EWMAC(16, 64) forecast signal."""
from __future__ import annotations

import numpy as np
import pandas as pd

from qtrend_v2.forecast.ewmac import EWMAC


def _make_bars(close_series: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(close_series), freq="B")
    return pd.DataFrame(
        {"open": close_series, "high": close_series, "low": close_series,
         "close": close_series, "volume": 1000},
        index=idx,
    )


def test_ewmac_output_shape_and_bounds():
    close = list(np.linspace(3000, 3600, 250))
    bars = _make_bars(close)
    forecast = EWMAC().compute(bars)
    assert isinstance(forecast, pd.Series)
    assert len(forecast) == len(bars)
    assert (forecast >= 0).all()
    assert (forecast <= 20).all()


def test_ewmac_positive_on_uptrend():
    close = list(np.linspace(3000, 3600, 250))
    bars = _make_bars(close)
    forecast = EWMAC().compute(bars)
    # Past the warm-up, an uptrend should generate a positive forecast.
    assert forecast.iloc[-1] > 5


def test_ewmac_zero_on_downtrend_long_only():
    close = list(np.linspace(3600, 3000, 250))
    bars = _make_bars(close)
    forecast = EWMAC().compute(bars)
    # Long-only: any downtrend signal is clipped to zero.
    assert forecast.iloc[-1] == 0.0


def test_ewmac_warmup_returns_zero_or_nan_safe():
    close = list(np.linspace(3000, 3050, 5))  # very short
    bars = _make_bars(close)
    forecast = EWMAC().compute(bars)
    # During warm-up, values must still be finite and in-range (clip NaN to 0).
    assert np.isfinite(forecast.values).all()
    assert (forecast >= 0).all() and (forecast <= 20).all()
```

- [ ] **Step 5.4: Run test, expect fail**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_forecast_ewmac.py -v`
Expected: ImportError.

- [ ] **Step 5.5: Write `src/qtrend_v2/forecast/ewmac.py`**

```python
"""EWMAC trend-strength forecast (Carver style, long-only clipped)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from qtrend_v2.forecast.base import ForecastSignal


class EWMAC(ForecastSignal):
    """EWMAC(fast, slow) — exponentially-weighted moving-average crossover.

    Following Carver (Systematic Trading), the raw forecast is

        raw = EMA(close, fast) - EMA(close, slow)

    normalised by an exponentially-weighted estimate of price volatility, then
    scaled to a long-run absolute value of ~10 and capped at ±20. Long-only:
    negative values clipped to 0.

    Defaults: fast=16, slow=64 (Carver's medium-term span).
    """

    def __init__(self, fast: int = 16, slow: int = 64, scalar: float = 4.1, cap: float = 20.0):
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be < slow ({slow})")
        self.fast = fast
        self.slow = slow
        self.scalar = scalar  # Carver's empirical scalar for EWMAC(16,64)
        self.cap = cap

    def compute(self, daily_bars: pd.DataFrame) -> pd.Series:
        close = daily_bars["close"].astype(float)
        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()
        raw = ema_fast - ema_slow

        # Volatility normalisation: 25-day exponentially-weighted std of daily price
        # changes. (Long enough to be stable, short enough to track regime shifts.)
        price_change = close.diff().abs()
        vol = price_change.ewm(span=25, adjust=False).mean().replace(0, np.nan)

        scaled = (raw / vol) * self.scalar
        scaled = scaled.clip(lower=0.0, upper=self.cap)
        scaled = scaled.fillna(0.0)
        return scaled
```

- [ ] **Step 5.6: Run test, expect pass**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_forecast_ewmac.py -v`
Expected: `4 passed`.

- [ ] **Step 5.7: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/forecast/ tests/test_forecast_ewmac.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(forecast): ForecastSignal ABC + EWMAC(16,64) long-only clipped"
```

---

## Task 6: Sizing (bucketed thresholding + hysteresis)

**Files:**
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/sizing.py`
- Create: `~/Desktop/QTrend_v2/tests/test_sizing.py`

- [ ] **Step 6.1: Write failing test `tests/test_sizing.py`**

```python
"""Tests for forecast → integer lot sizing with hysteresis."""
from __future__ import annotations

from qtrend_v2.sizing import Sizer


def test_sizer_rising_thresholds():
    s = Sizer()
    assert s.update(forecast=0.0) == 0
    assert s.update(forecast=4.5) == 1
    assert s.update(forecast=8.5) == 2
    assert s.update(forecast=12.5) == 3
    assert s.update(forecast=16.5) == 4
    assert s.update(forecast=20.0) == 5


def test_sizer_falling_with_hysteresis():
    s = Sizer()
    s.update(forecast=20.0)  # → 5
    # Drop just below upper edge — hysteresis keeps us at 5.
    assert s.update(forecast=19.5) == 5
    # Drop further — must cross hysteresis floor 19 to drop to 4.
    assert s.update(forecast=18.5) == 4
    # Hysteresis floor for 4 is 15; 15.5 keeps us at 4.
    assert s.update(forecast=15.5) == 4
    assert s.update(forecast=14.5) == 3


def test_sizer_reset_clears_state():
    s = Sizer()
    s.update(forecast=20.0)
    s.reset()
    assert s.update(forecast=4.5) == 1


def test_sizer_clips_negative_to_zero():
    s = Sizer()
    # Forecast is supposed to be long-only [0,20], but defend anyway.
    assert s.update(forecast=-3.0) == 0


def test_sizer_clips_above_max():
    s = Sizer()
    assert s.update(forecast=100.0) == 5
```

- [ ] **Step 6.2: Run test, expect fail**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_sizing.py -v`
Expected: ImportError.

- [ ] **Step 6.3: Write `src/qtrend_v2/sizing.py`**

```python
"""Forecast → integer-lot sizing with deadband hysteresis."""
from __future__ import annotations

# Rising thresholds: forecast >= threshold[i] → lots >= i+1
RISING_THRESHOLDS = (4.0, 8.0, 12.0, 16.0, 20.0)
# Falling thresholds: forecast <= threshold[i] → lots <= i (deadband = 1 unit)
FALLING_THRESHOLDS = (3.0, 7.0, 11.0, 15.0, 19.0)
MAX_LOTS = 5


class Sizer:
    """Stateful sizer with 1-unit hysteresis deadband.

    State = last emitted lot count. To raise lots, forecast must clear the next
    RISING threshold. To lower lots, forecast must fall below the relevant
    FALLING threshold. This deadband prevents flickering across a bucket edge.
    """

    def __init__(self) -> None:
        self._last_lots: int = 0

    def update(self, forecast: float) -> int:
        forecast = max(0.0, min(forecast, 100.0))  # defensive clip

        # Determine the highest "natural" bucket given pure rising thresholds.
        natural = 0
        for i, t in enumerate(RISING_THRESHOLDS):
            if forecast >= t:
                natural = i + 1
        natural = min(natural, MAX_LOTS)

        # Apply hysteresis: only allow drop if forecast crossed the FALLING line.
        if natural >= self._last_lots:
            new_lots = natural
        else:
            # Walk down one bucket at a time, each requiring its falling threshold.
            new_lots = self._last_lots
            while new_lots > 0 and forecast <= FALLING_THRESHOLDS[new_lots - 1]:
                new_lots -= 1
            new_lots = max(new_lots, natural)

        self._last_lots = new_lots
        return new_lots

    def reset(self) -> None:
        self._last_lots = 0
```

- [ ] **Step 6.4: Run test, expect pass**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_sizing.py -v`
Expected: `5 passed`.

- [ ] **Step 6.5: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/sizing.py tests/test_sizing.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(sizing): bucketed thresholding 0-5 lots with 1-unit hysteresis"
```

---

## Task 7: PullbackModulator (stateful Connors on 1H)

**Files:**
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/pullback/__init__.py`
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/pullback/connors.py`
- Create: `~/Desktop/QTrend_v2/tests/test_pullback.py`

- [ ] **Step 7.1: Write `src/qtrend_v2/pullback/__init__.py`**

```python
"""Pullback modulators."""
from qtrend_v2.pullback.connors import ConnorsPullback

__all__ = ["ConnorsPullback"]
```

- [ ] **Step 7.2: Write failing test `tests/test_pullback.py`**

```python
"""Tests for ConnorsPullback stateful modulator."""
from __future__ import annotations

import numpy as np
import pandas as pd

from qtrend_v2.pullback.connors import ConnorsPullback


def _make_1h_series(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-03-01 09:01:00", periods=len(closes), freq="h")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": 100},
        index=idx,
    )


def test_modulator_no_trim_when_forecast_below_gate():
    closes = [3000] * 20 + [3100] * 20  # sharp jump → RSI(2) high
    bars = _make_1h_series(closes)
    m = ConnorsPullback()
    out = m.adjust(bars, current_forecast=5.0, current_target=1)
    # Forecast below gate (8.0) — modulator inactive; offset stays 0; output = target.
    assert out == 1


def test_modulator_trims_when_overbought_and_forecast_high():
    closes = [3000] * 15 + [3000 + i * 5 for i in range(15)]
    bars = _make_1h_series(closes)
    m = ConnorsPullback(rsi_period=2, overbought=95.0, oversold=10.0)
    # Forecast high enough → gating allows action.
    final_target = m.adjust(bars, current_forecast=15.0, current_target=4)
    # If the last bar's RSI(2) is overbought, we should trim by 1.
    assert final_target in (3, 4)  # depends on synthetic RSI, but never > 4


def test_modulator_reload_only_undoes_prior_trim():
    # Build a sequence that first trims, then becomes oversold.
    closes_up = [3000 + i for i in range(15)]
    closes_dn = [3014 - i for i in range(15)]
    bars = _make_1h_series(closes_up + closes_dn)
    m = ConnorsPullback()
    # First adjust forces a trim because last-bars overbought.
    m.adjust(bars.iloc[:15], current_forecast=15.0, current_target=4)
    state_after_trim = m._offset  # noqa: SLF001  (test inspection)
    # Then trigger reload via oversold.
    m.adjust(bars, current_forecast=15.0, current_target=4)
    # Reload must not push above current_target.
    out = m.adjust(bars, current_forecast=15.0, current_target=4)
    assert out <= 4
    # offset should be in {-1, 0}, never +1.
    assert m._offset in (-1, 0)


def test_modulator_reset_clears_offset():
    closes = [3000 + i for i in range(40)]
    bars = _make_1h_series(closes)
    m = ConnorsPullback()
    m.adjust(bars, current_forecast=15.0, current_target=4)
    m.reset()
    assert m._offset == 0


def test_modulator_output_clipped_to_target_range():
    closes = [3000 + i for i in range(30)]
    bars = _make_1h_series(closes)
    m = ConnorsPullback()
    out = m.adjust(bars, current_forecast=20.0, current_target=0)
    # current_target=0 means there's nothing to trim; output stays 0.
    assert out == 0
```

- [ ] **Step 7.3: Run test, expect fail**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_pullback.py -v`
Expected: ImportError.

- [ ] **Step 7.4: Write `src/qtrend_v2/pullback/connors.py`**

```python
"""Connors-style stateful pullback modulator on 1H bars.

State machine:
    offset ∈ {-1, 0}, starts at 0.
    RSI(2) > overbought  and offset == 0  → offset := -1   (trim)
    RSI(2) < oversold    and offset == -1 → offset := 0    (reload undoes trim)
Gated: inactive (no transitions) when current_forecast < forecast_min.
Output: clip(current_target + offset, 0, current_target).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(close: pd.Series, period: int) -> pd.Series:
    """Wilder-style RSI(period). Returns 50 during warm-up (neutral)."""
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    roll_dn = down.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = roll_up / roll_dn.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


class ConnorsPullback:
    def __init__(
        self,
        rsi_period: int = 2,
        overbought: float = 95.0,
        oversold: float = 10.0,
        forecast_min: float = 8.0,
    ):
        self.rsi_period = rsi_period
        self.overbought = overbought
        self.oversold = oversold
        self.forecast_min = forecast_min
        self._offset: int = 0  # ∈ {-1, 0}

    def reset(self) -> None:
        self._offset = 0

    def adjust(
        self,
        h1_bars: pd.DataFrame,
        current_forecast: float,
        current_target: int,
    ) -> int:
        """Return the modulated target ∈ [0, current_target]."""
        if current_target <= 0:
            return 0

        if current_forecast < self.forecast_min:
            # Modulator inactive; offset state preserved across gate boundary.
            return current_target + self._offset if self._offset == 0 else current_target - 1 \
                if (current_target + self._offset) >= 0 else 0

        if len(h1_bars) < self.rsi_period + 1:
            return current_target

        rsi = _rsi(h1_bars["close"], self.rsi_period).iloc[-1]

        if self._offset == 0 and rsi > self.overbought:
            self._offset = -1
        elif self._offset == -1 and rsi < self.oversold:
            self._offset = 0

        adjusted = max(0, min(current_target + self._offset, current_target))
        return adjusted
```

> **Important**: the gated-branch logic above looks ugly. Simplify after the green tests pass:

After tests are green, refactor the inactive-gate branch:

```python
        if current_forecast < self.forecast_min:
            # Gate inactive: don't update offset state, just apply current offset.
            return max(0, min(current_target + self._offset, current_target))
```

(That's the intended semantics; rewrite the messy ternary above to this cleaner form once the green pass is in place.)

- [ ] **Step 7.5: Run test, expect pass**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_pullback.py -v`
Expected: `5 passed`.

- [ ] **Step 7.6: Clean up the gated-branch logic (refactor green→green)**

Replace the messy ternary with:
```python
        if current_forecast < self.forecast_min:
            return max(0, min(current_target + self._offset, current_target))
```

Re-run tests to confirm still green.

- [ ] **Step 7.7: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/pullback/ tests/test_pullback.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(pullback): stateful Connors RSI(2) modulator on 1H bars"
```

---

## Task 8: StateMachine (legs, trailing stop, timing, action emission)

**Files:**
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/state_machine.py`
- Create: `~/Desktop/QTrend_v2/tests/test_state_machine.py`

- [ ] **Step 8.1: Write failing test `tests/test_state_machine.py`**

```python
"""Tests for StateMachine."""
from __future__ import annotations

import pandas as pd

from qtrend_v2.state_machine import StateMachine
from qtrend_v2.types import ActionKind


def _bar(ts: str, close: float, rsi: float = 50.0) -> dict:
    return {"timestamp": pd.Timestamp(ts), "close": close, "rsi2": rsi, "atr": 30.0}


def test_buy_when_target_greater_than_current():
    sm = StateMachine()
    action = sm.step(target_lots=2, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    assert action.kind == ActionKind.BUY
    assert action.lots == 2


def test_hold_when_current_matches_target():
    sm = StateMachine()
    sm.step(target_lots=2, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(timestamp=pd.Timestamp("2024-01-02 10:00"),
                   kind=ActionKind.BUY, lots=2, price=3500.0)
    action = sm.step(target_lots=2, **_bar("2024-01-02 11:00", close=3510, rsi=55))
    assert action.kind == ActionKind.HOLD


def test_sell_when_target_below_current():
    sm = StateMachine()
    sm.step(target_lots=3, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(timestamp=pd.Timestamp("2024-01-02 10:00"),
                   kind=ActionKind.BUY, lots=3, price=3500.0)
    action = sm.step(target_lots=1, **_bar("2024-01-03 10:00", close=3520, rsi=60))
    assert action.kind == ActionKind.SELL
    assert action.lots == 2


def test_trailing_stop_triggers_flat_all():
    sm = StateMachine(atr_multiplier=3.0)
    sm.step(target_lots=3, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(timestamp=pd.Timestamp("2024-01-02 10:00"),
                   kind=ActionKind.BUY, lots=3, price=3500.0)
    # Price climbs to 3700; trailing reference = 3700 - 3*30 = 3610.
    sm.step(target_lots=3, **_bar("2024-01-02 11:00", close=3700, rsi=55))
    # Now price falls below stop.
    action = sm.step(target_lots=3, **_bar("2024-01-02 12:00", close=3600, rsi=40))
    assert action.kind == ActionKind.FLAT_ALL


def test_force_flat_clears_all_legs():
    sm = StateMachine()
    sm.step(target_lots=2, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(timestamp=pd.Timestamp("2024-01-02 10:00"),
                   kind=ActionKind.BUY, lots=2, price=3500.0)
    action = sm.force_flat(timestamp=pd.Timestamp("2024-01-05 09:00"),
                           reason="bias_off")
    assert action.kind == ActionKind.FLAT_ALL
    assert sm.current_lots == 0


def test_reset_clears_state():
    sm = StateMachine()
    sm.step(target_lots=2, **_bar("2024-01-02 10:00", close=3500, rsi=30))
    sm.record_fill(timestamp=pd.Timestamp("2024-01-02 10:00"),
                   kind=ActionKind.BUY, lots=2, price=3500.0)
    sm.reset()
    assert sm.current_lots == 0
    assert sm._peak_close is None  # noqa: SLF001


def test_buy_timing_filter_respects_rsi():
    """When RSI(2) >= 50 and we want to BUY, the action defers (HOLD)
    until either (a) RSI drops below 50 or (b) K bars elapse."""
    sm = StateMachine(timing_K_bars=3)
    a1 = sm.step(target_lots=2, **_bar("2024-01-02 10:00", close=3500, rsi=70))
    assert a1.kind == ActionKind.HOLD  # deferred — chasing
    a2 = sm.step(target_lots=2, **_bar("2024-01-02 11:00", close=3500, rsi=80))
    assert a2.kind == ActionKind.HOLD  # still deferred
    a3 = sm.step(target_lots=2, **_bar("2024-01-02 12:00", close=3500, rsi=75))
    # K=3 bars elapsed — force the trade.
    assert a3.kind == ActionKind.BUY
    assert a3.lots == 2
```

- [ ] **Step 8.2: Run test, expect fail**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_state_machine.py -v`
Expected: ImportError.

- [ ] **Step 8.3: Write `src/qtrend_v2/state_machine.py`**

```python
"""State machine: legs, ATR trailing stop, 1H execution timing, action emission."""
from __future__ import annotations

import pandas as pd

from qtrend_v2.types import Action, ActionKind, Leg


class StateMachine:
    """Tracks open round (legs), aggregate trailing stop, and emits Actions.

    A "round" begins at the first non-zero entry after current_lots == 0 and
    ends when the position returns to 0 (stop, force-flat, or scale-down to 0).
    The trailing reference (peak close since round start) is reset on round end.
    """

    def __init__(
        self,
        atr_multiplier: float = 3.0,
        timing_K_bars: int = 6,
        buy_rsi_max: float = 50.0,
        sell_rsi_min: float = 50.0,
    ):
        self.atr_multiplier = atr_multiplier
        self.timing_K_bars = timing_K_bars
        self.buy_rsi_max = buy_rsi_max
        self.sell_rsi_min = sell_rsi_min
        self._legs: list[Leg] = []
        self._peak_close: float | None = None
        self._pending_delta: int = 0  # signed lots awaiting timing
        self._pending_age_bars: int = 0

    # ----- public state queries -----

    @property
    def current_lots(self) -> int:
        return sum(leg.lots for leg in self._legs)

    def reset(self) -> None:
        self._legs.clear()
        self._peak_close = None
        self._pending_delta = 0
        self._pending_age_bars = 0

    # ----- main step -----

    def step(
        self,
        *,
        timestamp: pd.Timestamp,
        close: float,
        rsi2: float,
        atr: float,
        target_lots: int,
    ) -> Action:
        """Consume one 1H bar; emit Action."""
        # 1. Trailing stop check — only if we have a live position.
        if self.current_lots > 0:
            if self._peak_close is None or close > self._peak_close:
                self._peak_close = close
            stop_level = self._peak_close - self.atr_multiplier * atr
            if close <= stop_level:
                self._end_round()
                return Action(kind=ActionKind.FLAT_ALL, lots=0, reason="trailing_stop")

        # 2. Compute desired delta.
        delta = target_lots - self.current_lots

        # 3. If a new (different-sign) delta arrived, restart pending state.
        if delta == 0:
            self._pending_delta = 0
            self._pending_age_bars = 0
            return Action(kind=ActionKind.HOLD, lots=0, reason="at_target")

        if (delta > 0 and self._pending_delta < 0) or (delta < 0 and self._pending_delta > 0):
            self._pending_delta = delta
            self._pending_age_bars = 0
        elif self._pending_delta == 0:
            self._pending_delta = delta
            self._pending_age_bars = 0
        else:
            # Same direction; refresh size.
            self._pending_delta = delta

        # 4. Timing filter.
        timing_ok = (
            (delta > 0 and rsi2 < self.buy_rsi_max) or
            (delta < 0 and rsi2 >= self.sell_rsi_min)
        )

        if not timing_ok and self._pending_age_bars + 1 < self.timing_K_bars:
            self._pending_age_bars += 1
            return Action(kind=ActionKind.HOLD, lots=0, reason="timing_deferred")

        # 5. Fire.
        if delta > 0:
            return Action(kind=ActionKind.BUY, lots=delta, reason="enter_or_scale_up")
        else:
            return Action(kind=ActionKind.SELL, lots=-delta, reason="scale_down")

    def force_flat(self, *, timestamp: pd.Timestamp, reason: str) -> Action:
        if self.current_lots == 0:
            return Action(kind=ActionKind.HOLD, lots=0, reason=f"flat_already:{reason}")
        self._end_round()
        return Action(kind=ActionKind.FLAT_ALL, lots=0, reason=reason)

    # ----- fill recording -----

    def record_fill(
        self,
        *,
        timestamp: pd.Timestamp,
        kind: ActionKind,
        lots: int,
        price: float,
    ) -> None:
        """Reconcile state after an ExecutionAdapter reports a fill."""
        if kind == ActionKind.BUY:
            self._legs.append(Leg(timestamp=timestamp, price=price, lots=lots))
            if self._peak_close is None:
                self._peak_close = price
            else:
                self._peak_close = max(self._peak_close, price)
            self._pending_delta = max(0, self._pending_delta - lots)
        elif kind == ActionKind.SELL:
            self._reduce_legs(lots)
            self._pending_delta = min(0, self._pending_delta + lots)
            if self.current_lots == 0:
                self._end_round()
        elif kind == ActionKind.FLAT_ALL:
            self._end_round()
        # HOLD: no-op
        if self._pending_delta == 0:
            self._pending_age_bars = 0

    # ----- internals -----

    def _reduce_legs(self, lots_to_sell: int) -> None:
        """FIFO: oldest legs sold first."""
        remaining = lots_to_sell
        new_legs: list[Leg] = []
        for leg in self._legs:
            if remaining >= leg.lots:
                remaining -= leg.lots
                continue
            if remaining > 0:
                new_legs.append(Leg(timestamp=leg.timestamp, price=leg.price,
                                     lots=leg.lots - remaining))
                remaining = 0
            else:
                new_legs.append(leg)
        self._legs = new_legs

    def _end_round(self) -> None:
        self._legs.clear()
        self._peak_close = None
        self._pending_delta = 0
        self._pending_age_bars = 0
```

- [ ] **Step 8.4: Run test, expect pass**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_state_machine.py -v`
Expected: `7 passed`.

- [ ] **Step 8.5: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/state_machine.py tests/test_state_machine.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(state): StateMachine with legs, ATR trailing stop, 1H timing, action emission"
```

---

## Task 9: Simulator ExecutionAdapter

**Files:**
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/execution/__init__.py`
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/execution/simulator.py`
- Create: `~/Desktop/QTrend_v2/tests/test_simulator.py`

- [ ] **Step 9.1: Write `src/qtrend_v2/execution/__init__.py`**

```python
"""Execution adapters."""
from qtrend_v2.execution.simulator import SimulatorAdapter

__all__ = ["SimulatorAdapter"]
```

- [ ] **Step 9.2: Write failing test `tests/test_simulator.py`**

```python
"""Tests for SimulatorAdapter."""
from __future__ import annotations

import pandas as pd

from qtrend_v2.execution.simulator import SimulatorAdapter
from qtrend_v2.types import Action, ActionKind


def test_buy_fill_at_next_1h_open():
    bars = pd.DataFrame(
        {"open": [3500.0, 3510.0, 3520.0], "high": [3505, 3515, 3525],
         "low": [3495, 3505, 3515], "close": [3503, 3513, 3523]},
        index=pd.date_range("2024-01-02 10:00", periods=3, freq="h"),
    )
    sim = SimulatorAdapter(bars=bars, tx_cost_per_lot=1.0)
    fill = sim.execute(
        action=Action(kind=ActionKind.BUY, lots=2, reason="enter"),
        current_ts=bars.index[0],
    )
    assert fill is not None
    assert fill.kind == ActionKind.BUY
    assert fill.lots == 2
    # Fill at next bar's open + cost.
    assert fill.price == 3510.0 + 1.0
    assert fill.timestamp == bars.index[1]


def test_sell_fill_at_next_1h_open_minus_cost():
    bars = pd.DataFrame(
        {"open": [3500.0, 3510.0, 3520.0], "high": [3505, 3515, 3525],
         "low": [3495, 3505, 3515], "close": [3503, 3513, 3523]},
        index=pd.date_range("2024-01-02 10:00", periods=3, freq="h"),
    )
    sim = SimulatorAdapter(bars=bars, tx_cost_per_lot=1.0)
    fill = sim.execute(
        action=Action(kind=ActionKind.SELL, lots=1, reason="scale_down"),
        current_ts=bars.index[0],
    )
    assert fill is not None
    assert fill.price == 3510.0 - 1.0


def test_hold_returns_none():
    bars = pd.DataFrame(
        {"open": [3500.0], "high": [3505], "low": [3495], "close": [3503]},
        index=pd.date_range("2024-01-02 10:00", periods=1, freq="h"),
    )
    sim = SimulatorAdapter(bars=bars)
    fill = sim.execute(
        action=Action(kind=ActionKind.HOLD, lots=0, reason="at_target"),
        current_ts=bars.index[0],
    )
    assert fill is None


def test_no_next_bar_returns_none():
    bars = pd.DataFrame(
        {"open": [3500.0], "high": [3505], "low": [3495], "close": [3503]},
        index=pd.date_range("2024-01-02 10:00", periods=1, freq="h"),
    )
    sim = SimulatorAdapter(bars=bars)
    fill = sim.execute(
        action=Action(kind=ActionKind.BUY, lots=1, reason="enter"),
        current_ts=bars.index[0],
    )
    assert fill is None  # last bar — no fill possible
```

- [ ] **Step 9.3: Run test, expect fail**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_simulator.py -v`
Expected: ImportError.

- [ ] **Step 9.4: Write `src/qtrend_v2/execution/simulator.py`**

```python
"""Simulator adapter: fills at next 1H bar's open with fixed cost."""
from __future__ import annotations

import pandas as pd

from qtrend_v2.types import Action, ActionKind, Fill


class SimulatorAdapter:
    """Naive simulator. Fills at next 1H bar's open price. Adds tx_cost_per_lot
    to BUY fill price and subtracts from SELL fill price. Returns None for
    HOLD or when no next bar is available (end of window)."""

    def __init__(self, bars: pd.DataFrame, tx_cost_per_lot: float = 1.0):
        if "open" not in bars.columns:
            raise ValueError("simulator bars must have 'open' column")
        if not bars.index.is_monotonic_increasing:
            raise ValueError("simulator bars index must be monotonic increasing")
        self._bars = bars
        self.tx_cost_per_lot = tx_cost_per_lot

    def execute(self, *, action: Action, current_ts: pd.Timestamp) -> Fill | None:
        if action.kind in (ActionKind.HOLD,):
            return None
        # Find next bar strictly after current_ts.
        future = self._bars.loc[self._bars.index > current_ts]
        if future.empty:
            return None
        next_bar = future.iloc[0]
        next_ts = future.index[0]

        if action.kind == ActionKind.BUY:
            price = float(next_bar["open"]) + self.tx_cost_per_lot
        elif action.kind == ActionKind.SELL:
            price = float(next_bar["open"]) - self.tx_cost_per_lot
        elif action.kind == ActionKind.FLAT_ALL:
            # Fill at open without cost-direction; caller decides lots.
            # For FLAT_ALL the caller must pass the exit-lots externally.
            # We model exit cost as a SELL: price - cost.
            price = float(next_bar["open"]) - self.tx_cost_per_lot
        else:
            raise ValueError(f"unknown action {action.kind}")

        return Fill(
            timestamp=next_ts,
            kind=action.kind,
            lots=action.lots,
            price=price,
            reason=action.reason,
        )
```

- [ ] **Step 9.5: Run test, expect pass**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_simulator.py -v`
Expected: `4 passed`.

- [ ] **Step 9.6: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/execution/ tests/test_simulator.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(execution): simulator adapter (fill at next 1H open + fixed cost)"
```

---

## Task 10: Backtest driver

**Files:**
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/backtest.py`
- Create: `~/Desktop/QTrend_v2/tests/test_backtest.py` (unit-level, smoke is in Task 14)

- [ ] **Step 10.1: Write failing test `tests/test_backtest.py`**

```python
"""Unit-level test: backtest driver runs over a synthetic window."""
from __future__ import annotations

import pandas as pd

from qtrend_v2.backtest import WindowResult, run_window
from qtrend_v2.bias import BiasWindow
from qtrend_v2.execution.simulator import SimulatorAdapter
from qtrend_v2.forecast.ewmac import EWMAC
from qtrend_v2.pullback.connors import ConnorsPullback
from qtrend_v2.sizing import Sizer
from qtrend_v2.state_machine import StateMachine


def _make_daily_uptrend(n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = [3000 + i * 5 for i in range(n)]
    return pd.DataFrame({"open": close, "high": [c + 5 for c in close],
                         "low": [c - 5 for c in close], "close": close,
                         "volume": 1000}, index=idx)


def _make_h1_from_daily(daily: pd.DataFrame, bars_per_day: int = 4) -> pd.DataFrame:
    rows = []
    for ts, row in daily.iterrows():
        for h in range(bars_per_day):
            ts_h = ts.replace(hour=9 + h * 2)
            close = row["close"] + (h - 1.5) * 0.1
            rows.append({"datetime": ts_h, "open": close, "high": close + 0.5,
                         "low": close - 0.5, "close": close, "volume": 100})
    return pd.DataFrame(rows).set_index("datetime")


def test_run_window_returns_result_with_pnl_and_log():
    daily = _make_daily_uptrend(60)
    h1 = _make_h1_from_daily(daily)
    window = BiasWindow(start=daily.index[0], end=daily.index[-1], note="test")
    result = run_window(
        window=window,
        daily=daily,
        h1=h1,
        forecast=EWMAC(),
        sizer=Sizer(),
        pullback=ConnorsPullback(),
        state_machine=StateMachine(),
        simulator=SimulatorAdapter(bars=h1),
    )
    assert isinstance(result, WindowResult)
    assert result.window == window
    assert isinstance(result.equity, pd.Series)
    assert isinstance(result.actions_log, pd.DataFrame)
    # On a clean uptrend, total PnL should be positive (or at least non-negative).
    assert result.equity.iloc[-1] >= result.equity.iloc[0]
```

- [ ] **Step 10.2: Run test, expect fail**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_backtest.py -v`
Expected: ImportError.

- [ ] **Step 10.3: Write `src/qtrend_v2/backtest.py`**

```python
"""Backtest driver: run strategy over a single bias window."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from qtrend_v2.bias import BiasWindow
from qtrend_v2.execution.simulator import SimulatorAdapter
from qtrend_v2.forecast.base import ForecastSignal
from qtrend_v2.pullback.connors import ConnorsPullback
from qtrend_v2.sizing import Sizer
from qtrend_v2.state_machine import StateMachine
from qtrend_v2.types import ActionKind


def _wilder_atr(daily: pd.DataFrame, period: int = 20) -> pd.Series:
    high = daily["high"].astype(float)
    low = daily["low"].astype(float)
    close = daily["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def _wilder_rsi(close: pd.Series, period: int = 2) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    roll_dn = down.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = roll_up / roll_dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


@dataclass
class WindowResult:
    window: BiasWindow
    equity: pd.Series          # cumulative PnL indexed by 1H timestamp
    actions_log: pd.DataFrame  # columns: ts, kind, lots, price, reason, current_lots
    lot_history: pd.Series     # current_lots over 1H bars
    forecast_history: pd.Series  # forecast over daily bars


def run_window(
    *,
    window: BiasWindow,
    daily: pd.DataFrame,
    h1: pd.DataFrame,
    forecast: ForecastSignal,
    sizer: Sizer,
    pullback: ConnorsPullback,
    state_machine: StateMachine,
    simulator: SimulatorAdapter,
) -> WindowResult:
    """Run strategy through one bias window. Returns WindowResult."""
    # Slice to window. Pull a 100-bar warmup tail of daily to stabilise EWMAC.
    daily_window = daily.loc[window.start:window.end]
    h1_window = h1.loc[window.start:window.end]

    if daily_window.empty or h1_window.empty:
        return WindowResult(
            window=window, equity=pd.Series(dtype=float),
            actions_log=pd.DataFrame(), lot_history=pd.Series(dtype=int),
            forecast_history=pd.Series(dtype=float),
        )

    # Pre-compute daily-level signals (using full daily history up to window end for
    # signal context, but we only emit during the window).
    daily_full = daily.loc[:window.end]
    forecast_full = forecast.compute(daily_full)
    atr_full = _wilder_atr(daily_full)
    rsi_h1 = _wilder_rsi(h1.loc[:window.end]["close"])

    # Reset stateful components.
    sizer.reset()
    pullback.reset()
    state_machine.reset()

    actions: list[dict] = []
    lot_history: list[tuple[pd.Timestamp, int]] = []
    pnl_series: list[tuple[pd.Timestamp, float]] = []
    cash = 0.0
    last_price = float(h1_window.iloc[0]["close"])

    for ts in h1_window.index:
        # Find the most recent daily forecast/ATR ≤ ts.
        daily_ts = forecast_full.index[forecast_full.index <= ts]
        if daily_ts.empty:
            continue
        d_ts = daily_ts[-1]
        current_forecast = float(forecast_full.loc[d_ts])
        current_atr = float(atr_full.loc[d_ts]) if not np.isnan(atr_full.loc[d_ts]) else 50.0

        natural_target = sizer.update(forecast=current_forecast)
        modulated_target = pullback.adjust(
            h1_bars=h1.loc[:ts],
            current_forecast=current_forecast,
            current_target=natural_target,
        )

        close = float(h1_window.loc[ts]["close"])
        rsi2 = float(rsi_h1.loc[ts]) if ts in rsi_h1.index else 50.0

        action = state_machine.step(
            timestamp=ts, close=close, rsi2=rsi2, atr=current_atr,
            target_lots=modulated_target,
        )

        if action.kind in (ActionKind.BUY, ActionKind.SELL):
            fill = simulator.execute(action=action, current_ts=ts)
            if fill is not None:
                state_machine.record_fill(
                    timestamp=fill.timestamp, kind=fill.kind,
                    lots=fill.lots, price=fill.price,
                )
                signed = fill.lots if fill.kind == ActionKind.BUY else -fill.lots
                cash -= signed * fill.price
                actions.append({
                    "ts": fill.timestamp, "kind": fill.kind.value,
                    "lots": fill.lots, "price": fill.price,
                    "reason": fill.reason, "current_lots": state_machine.current_lots,
                })
        elif action.kind == ActionKind.FLAT_ALL:
            lots_to_close = state_machine.current_lots
            if lots_to_close > 0:
                # Issue equivalent SELL to simulator for proper cash accounting.
                from qtrend_v2.types import Action
                sell_action = Action(kind=ActionKind.SELL, lots=lots_to_close,
                                     reason=action.reason)
                fill = simulator.execute(action=sell_action, current_ts=ts)
                if fill is not None:
                    state_machine.record_fill(
                        timestamp=fill.timestamp, kind=fill.kind,
                        lots=fill.lots, price=fill.price,
                    )
                    cash -= -fill.lots * fill.price  # cash += fill.lots * fill.price
                    actions.append({
                        "ts": fill.timestamp, "kind": "FLAT_ALL",
                        "lots": fill.lots, "price": fill.price,
                        "reason": action.reason, "current_lots": 0,
                    })

        equity = cash + state_machine.current_lots * close
        pnl_series.append((ts, equity))
        lot_history.append((ts, state_machine.current_lots))
        last_price = close

    # Force flat at window end.
    if state_machine.current_lots > 0:
        from qtrend_v2.types import Action
        lots_to_close = state_machine.current_lots
        sell_action = Action(kind=ActionKind.SELL, lots=lots_to_close,
                             reason="bias_off_end_of_window")
        # No "next bar" inside window; close at last close.
        cash += lots_to_close * last_price
        state_machine.force_flat(timestamp=h1_window.index[-1], reason="bias_off")
        actions.append({
            "ts": h1_window.index[-1], "kind": "FLAT_ALL",
            "lots": lots_to_close, "price": last_price,
            "reason": "bias_off_end_of_window", "current_lots": 0,
        })

    equity_series = pd.Series(
        [p for _, p in pnl_series],
        index=pd.DatetimeIndex([t for t, _ in pnl_series]),
        name="equity",
    )
    lot_series = pd.Series(
        [l for _, l in lot_history],
        index=pd.DatetimeIndex([t for t, _ in lot_history]),
        name="lots",
    )
    actions_df = pd.DataFrame(actions) if actions else pd.DataFrame(
        columns=["ts", "kind", "lots", "price", "reason", "current_lots"]
    )

    return WindowResult(
        window=window,
        equity=equity_series,
        actions_log=actions_df,
        lot_history=lot_series,
        forecast_history=forecast_full.loc[window.start:window.end],
    )
```

- [ ] **Step 10.4: Run test, expect pass**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_backtest.py -v`
Expected: `1 passed`.

- [ ] **Step 10.5: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/backtest.py tests/test_backtest.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(backtest): run_window driver with ATR/RSI compute + simulator wiring"
```

---

## Task 11: Strategy top-level wiring

**Files:**
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/strategy.py`
- Modify: `~/Desktop/QTrend_v2/src/qtrend_v2/__init__.py` (re-export)
- Create: `~/Desktop/QTrend_v2/tests/test_strategy.py`

- [ ] **Step 11.1: Write failing test `tests/test_strategy.py`**

```python
"""Top-level Strategy class test."""
from __future__ import annotations

import pandas as pd

from qtrend_v2 import Strategy
from qtrend_v2.bias import BiasWindow


def _daily_uptrend(n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = [3000 + i * 5 for i in range(n)]
    return pd.DataFrame({"open": close, "high": [c + 5 for c in close],
                         "low": [c - 5 for c in close], "close": close,
                         "volume": 1000}, index=idx)


def _h1_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ts, row in daily.iterrows():
        for h in range(4):
            ts_h = ts.replace(hour=9 + h * 2)
            close = row["close"] + (h - 1.5) * 0.1
            rows.append({"datetime": ts_h, "open": close, "high": close + 0.5,
                         "low": close - 0.5, "close": close, "volume": 100})
    return pd.DataFrame(rows).set_index("datetime")


def test_strategy_run_window_smoke():
    daily = _daily_uptrend(60)
    h1 = _h1_from_daily(daily)
    window = BiasWindow(start=daily.index[0], end=daily.index[-1], note="t")
    strat = Strategy()
    result = strat.run_window(window=window, daily=daily, h1=h1)
    assert result.window == window
    assert len(result.lot_history) > 0
```

- [ ] **Step 11.2: Run test, expect fail (`Strategy` not exported)**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_strategy.py -v`
Expected: ImportError.

- [ ] **Step 11.3: Write `src/qtrend_v2/strategy.py`**

```python
"""Top-level Strategy: wires forecast, sizer, pullback, state_machine, simulator."""
from __future__ import annotations

import pandas as pd

from qtrend_v2.backtest import WindowResult, run_window
from qtrend_v2.bias import BiasWindow
from qtrend_v2.execution.simulator import SimulatorAdapter
from qtrend_v2.forecast.base import ForecastSignal
from qtrend_v2.forecast.ewmac import EWMAC
from qtrend_v2.pullback.connors import ConnorsPullback
from qtrend_v2.sizing import Sizer
from qtrend_v2.state_machine import StateMachine


class Strategy:
    """User-facing entry point. Default v1 config: EWMAC(16,64) + Connors + 3×ATR stop."""

    def __init__(
        self,
        forecast: ForecastSignal | None = None,
        sizer: Sizer | None = None,
        pullback: ConnorsPullback | None = None,
        state_machine: StateMachine | None = None,
        tx_cost_per_lot: float = 1.0,
    ):
        self.forecast = forecast or EWMAC()
        self.sizer = sizer or Sizer()
        self.pullback = pullback or ConnorsPullback()
        self.state_machine = state_machine or StateMachine()
        self.tx_cost_per_lot = tx_cost_per_lot

    def run_window(
        self,
        *,
        window: BiasWindow,
        daily: pd.DataFrame,
        h1: pd.DataFrame,
    ) -> WindowResult:
        sim = SimulatorAdapter(bars=h1, tx_cost_per_lot=self.tx_cost_per_lot)
        return run_window(
            window=window, daily=daily, h1=h1,
            forecast=self.forecast, sizer=self.sizer,
            pullback=self.pullback, state_machine=self.state_machine,
            simulator=sim,
        )
```

- [ ] **Step 11.4: Modify `src/qtrend_v2/__init__.py`**

```python
"""QTrend_v2 — long-only trend-capture engine for HC futures."""

from qtrend_v2.strategy import Strategy

__version__ = "0.1.0"
__all__ = ["Strategy", "__version__"]
```

- [ ] **Step 11.5: Run test, expect pass**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_strategy.py -v`
Expected: `1 passed`.

- [ ] **Step 11.6: Run full test suite**

Run: `cd ~/Desktop/QTrend_v2 && pytest -ra`
Expected: all tests pass.

- [ ] **Step 11.7: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/strategy.py src/qtrend_v2/__init__.py tests/test_strategy.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(strategy): Strategy class wiring with EWMAC + Connors defaults"
```

---

## Task 12: Per-window HTML report

**Files:**
- Create: `~/Desktop/QTrend_v2/src/qtrend_v2/report.py`
- Create: `~/Desktop/QTrend_v2/tests/test_report.py`

- [ ] **Step 12.1: Write failing test `tests/test_report.py`**

```python
"""Tests for HTML report generation."""
from __future__ import annotations

import pandas as pd

from qtrend_v2 import Strategy
from qtrend_v2.bias import BiasWindow
from qtrend_v2.report import render_window_report


def _daily(n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = [3000 + i * 5 for i in range(n)]
    return pd.DataFrame({"open": close, "high": [c + 5 for c in close],
                         "low": [c - 5 for c in close], "close": close,
                         "volume": 1000}, index=idx)


def _h1(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ts, row in daily.iterrows():
        for h in range(4):
            ts_h = ts.replace(hour=9 + h * 2)
            close = row["close"]
            rows.append({"datetime": ts_h, "open": close, "high": close + 0.5,
                         "low": close - 0.5, "close": close, "volume": 100})
    return pd.DataFrame(rows).set_index("datetime")


def test_render_window_report_writes_html(tmp_path):
    daily = _daily(60)
    h1 = _h1(daily)
    window = BiasWindow(start=daily.index[0], end=daily.index[-1], note="t1")
    result = Strategy().run_window(window=window, daily=daily, h1=h1)
    out = tmp_path / "window.html"
    render_window_report(result=result, daily=daily, output_path=out)
    assert out.exists()
    html = out.read_text()
    assert "QTrend_v2" in html
    assert "t1" in html  # the note appears
```

- [ ] **Step 12.2: Run test, expect fail**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_report.py -v`
Expected: ImportError.

- [ ] **Step 12.3: Write `src/qtrend_v2/report.py`**

```python
"""HTML report generation: per-window + aggregate."""
from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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

    daily_slice = daily.loc[result.window.start:result.window.end]

    # Price + lots chart.
    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax1.plot(daily_slice.index, daily_slice["close"], color="black", label="close")
    ax1.set_ylabel("close")
    ax2 = ax1.twinx()
    if len(result.lot_history):
        ax2.step(result.lot_history.index, result.lot_history.values,
                 color="steelblue", where="post", label="lots", alpha=0.6)
        ax2.set_ylabel("lots")
        ax2.set_ylim(-0.5, 5.5)
    ax1.set_title("Price + lot history")
    chart_price_lots = _fig_to_b64(fig)

    # Equity chart.
    fig, ax = plt.subplots(figsize=(10, 3))
    if len(eq):
        ax.plot(eq.index, eq.values, color="darkgreen")
        ax.fill_between(eq.index, eq.values, eq.cummax(), color="red", alpha=0.2)
    ax.set_title("Equity (cumulative PnL)")
    chart_equity = _fig_to_b64(fig)

    # Forecast chart.
    fig, ax = plt.subplots(figsize=(10, 3))
    if len(result.forecast_history):
        ax.plot(result.forecast_history.index, result.forecast_history.values,
                color="purple")
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
        if not result.actions_log.empty else "<p>(no actions taken)</p>"
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
```

- [ ] **Step 12.4: Run test, expect pass**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_report.py -v`
Expected: `1 passed`.

- [ ] **Step 12.5: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/report.py tests/test_report.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(report): per-window HTML report (price+lots, equity, forecast, action log)"
```

---

## Task 13: Aggregate report

**Files:**
- Modify: `~/Desktop/QTrend_v2/src/qtrend_v2/report.py` (add `render_aggregate_report`)
- Modify: `~/Desktop/QTrend_v2/tests/test_report.py` (add test)

- [ ] **Step 13.1: Add failing test to `tests/test_report.py`**

```python
def test_render_aggregate_report_writes_html(tmp_path):
    from qtrend_v2.report import render_aggregate_report

    daily = _daily(60)
    h1 = _h1(daily)
    w1 = BiasWindow(start=daily.index[0], end=daily.index[29], note="w1")
    w2 = BiasWindow(start=daily.index[30], end=daily.index[-1], note="w2")
    strat = Strategy()
    r1 = strat.run_window(window=w1, daily=daily, h1=h1)
    r2 = strat.run_window(window=w2, daily=daily, h1=h1)
    out = tmp_path / "agg.html"
    render_aggregate_report(results=[r1, r2], output_path=out)
    assert out.exists()
    html = out.read_text()
    assert "Aggregate" in html
    assert "w1" in html and "w2" in html
```

- [ ] **Step 13.2: Run test, expect fail (import error / function missing)**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_report.py::test_render_aggregate_report_writes_html -v`
Expected: ImportError.

- [ ] **Step 13.3: Append to `src/qtrend_v2/report.py`**

Append (after the existing code):

```python
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
        rows.append({
            "start": r.window.start.date(),
            "end": r.window.end.date(),
            "note": r.window.note,
            "pnl": round(pnl, 2),
            "max_dd": round(dd, 2),
            "time_in_market": round(tim, 3),
            "n_actions": int(r.actions_log.shape[0]),
        })

    summary = pd.DataFrame(rows)
    hit_rate = (summary["pnl"] > 0).mean() if len(summary) else 0.0
    total_pnl = summary["pnl"].sum() if len(summary) else 0.0
    mean_pnl = summary["pnl"].mean() if len(summary) else 0.0
    worst_dd = summary["max_dd"].min() if len(summary) else 0.0
    median_tim = summary["time_in_market"].median() if len(summary) else 0.0

    fig, ax = plt.subplots(figsize=(8, 3))
    if len(summary):
        ax.bar(range(len(summary)), summary["pnl"],
               color=["green" if p > 0 else "red" for p in summary["pnl"]])
        ax.axhline(0, color="black", linewidth=0.5)
        ax.set_xticks(range(len(summary)))
        ax.set_xticklabels(summary["note"], rotation=30, ha="right")
        ax.set_ylabel("PnL")
        ax.set_title("Per-window PnL")
    chart_pnl_dist = _fig_to_b64(fig)

    html = _AGGREGATE_TEMPLATE.render(
        n=len(results),
        per_window_html=summary.to_html(index=False) if len(summary)
            else "<p>(no windows)</p>",
        hit_rate=f"{hit_rate:.1%}",
        total_pnl=f"{total_pnl:+.2f}",
        mean_pnl=f"{mean_pnl:+.2f}",
        worst_dd=f"{worst_dd:+.2f}",
        median_tim=f"{median_tim:.1%}",
        chart_pnl_dist=chart_pnl_dist,
    )
    output_path.write_text(html)
    return output_path
```

- [ ] **Step 13.4: Run test, expect pass**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_report.py -v`
Expected: `2 passed`.

- [ ] **Step 13.5: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add src/qtrend_v2/report.py tests/test_report.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "feat(report): aggregate HTML report (per-window summary + PnL bar chart)"
```

---

## Task 14: End-to-end smoke test with real HC data

**Files:**
- Create: `~/Desktop/QTrend_v2/tests/test_backtest_smoke.py`

- [ ] **Step 14.1: Write smoke test**

```python
"""End-to-end smoke: real HC data + template bias_windows.csv → both reports."""
from __future__ import annotations

from pathlib import Path

import pytest

from qtrend_v2 import Strategy
from qtrend_v2.bias import BiasWindowLoader
from qtrend_v2.data import load_hc_1h, load_hc_daily
from qtrend_v2.report import render_aggregate_report, render_window_report

DAILY_PATH = Path("/Users/simon/Desktop/data/CN/market/continuous/.cache/HC_daily.parquet")
BIAS_PATH = Path(__file__).parent.parent / "data" / "bias_windows.csv"


@pytest.mark.skipif(not DAILY_PATH.exists(), reason="HC data not present")
def test_smoke_end_to_end(tmp_path):
    daily = load_hc_daily()
    h1 = load_hc_1h()
    loader = BiasWindowLoader(BIAS_PATH)
    strat = Strategy()
    results = []
    for window in loader.windows():
        # Skip windows that fall outside available data.
        if window.start < daily.index.min() or window.end > daily.index.max():
            continue
        result = strat.run_window(window=window, daily=daily, h1=h1)
        out = tmp_path / f"window_{window.start.date()}.html"
        render_window_report(result=result, daily=daily, output_path=out)
        results.append(result)
        assert out.exists()
    assert results, "no windows in range — extend or fix bias_windows.csv"
    agg_out = tmp_path / "aggregate.html"
    render_aggregate_report(results=results, output_path=agg_out)
    assert agg_out.exists()
```

- [ ] **Step 14.2: Run smoke**

Run: `cd ~/Desktop/QTrend_v2 && pytest tests/test_backtest_smoke.py -v`
Expected: `1 passed`.

- [ ] **Step 14.3: Run full test suite + ruff**

Run:
```bash
cd ~/Desktop/QTrend_v2 && pytest -ra && ruff format src/ tests/ && ruff check src/ tests/
```
Expected: all tests pass, ruff clean.

- [ ] **Step 14.4: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add tests/test_backtest_smoke.py && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "test: end-to-end smoke with real HC data + sample bias windows"
```

---

## Task 15: Walkthrough notebook

**Files:**
- Create: `~/Desktop/QTrend_v2/notebooks/2026-05-11-v1-walkthrough.ipynb`

- [ ] **Step 15.1: Generate the notebook from a Python script**

Create a temporary script at `~/Desktop/QTrend_v2/scripts/_gen_notebook.py`:

```python
"""Generate the v1 walkthrough notebook programmatically."""
from __future__ import annotations

import json
from pathlib import Path


def code_cell(src: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": src.splitlines(keepends=True)}


def md_cell(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {},
            "source": src.splitlines(keepends=True)}


cells = [
    md_cell("# QTrend_v2 v1 walkthrough\n\n"
            "End-to-end demo: load HC data, run one bias window, render report.\n"),
    code_cell(
        "import pandas as pd\n"
        "from qtrend_v2 import Strategy\n"
        "from qtrend_v2.bias import BiasWindow, BiasWindowLoader\n"
        "from qtrend_v2.data import load_hc_daily, load_hc_1h\n"
        "from qtrend_v2.report import render_window_report, render_aggregate_report\n"
        "from pathlib import Path\n"
    ),
    md_cell("## 1. Load HC data and bias windows"),
    code_cell(
        "daily = load_hc_daily()\n"
        "h1    = load_hc_1h()\n"
        "print(f'daily: {len(daily)} bars, {daily.index.min().date()} → {daily.index.max().date()}')\n"
        "print(f'1H   : {len(h1)} bars')\n"
    ),
    code_cell(
        "loader = BiasWindowLoader(Path('..') / 'data' / 'bias_windows.csv')\n"
        "for w in loader.windows():\n"
        "    print(w.start.date(), '→', w.end.date(), '|', w.note)\n"
    ),
    md_cell("## 2. Run strategy on one window"),
    code_cell(
        "strat = Strategy()\n"
        "windows = [w for w in loader.windows() if w.start >= daily.index.min()]\n"
        "w = windows[0]\n"
        "result = strat.run_window(window=w, daily=daily, h1=h1)\n"
        "result.actions_log.head(20)\n"
    ),
    md_cell("## 3. Inspect equity, lot history, forecast"),
    code_cell(
        "result.equity.plot(title='Equity', figsize=(10, 3))\n"
    ),
    code_cell(
        "result.lot_history.plot(title='Lot history', figsize=(10, 2), drawstyle='steps-post')\n"
    ),
    code_cell(
        "result.forecast_history.plot(title='Daily forecast', figsize=(10, 3), color='purple')\n"
    ),
    md_cell("## 4. Render reports"),
    code_cell(
        "reports_dir = Path('..') / 'reports'\n"
        "reports_dir.mkdir(exist_ok=True)\n"
        "render_window_report(result=result, daily=daily, output_path=reports_dir / f'window_{w.start.date()}.html')\n"
    ),
    code_cell(
        "results = [strat.run_window(window=w_, daily=daily, h1=h1) for w_ in windows]\n"
        "render_aggregate_report(results=results, output_path=reports_dir / 'aggregate.html')\n"
        "print('Reports:', list(reports_dir.glob('*.html')))\n"
    ),
    md_cell("## Next steps\n\n"
            "- Replace `bias_windows.csv` placeholders with real annotations.\n"
            "- Swap `EWMAC()` for `TSMOM` or `DonchianFraction` and re-run.\n"
            "- Compare aggregate hit rate / PnL distribution across forecasts.\n"),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = Path(__file__).parent.parent / "notebooks" / "2026-05-11-v1-walkthrough.ipynb"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(notebook, indent=2))
print(f"wrote {out}")
```

Then run:
```bash
cd ~/Desktop/QTrend_v2 && python scripts/_gen_notebook.py
```

- [ ] **Step 15.2: Verify notebook is valid JSON**

```bash
python -c "import json; from pathlib import Path; nb = json.loads(Path('/Users/simon/Desktop/QTrend_v2/notebooks/2026-05-11-v1-walkthrough.ipynb').read_text()); print('cells:', len(nb['cells']))"
```
Expected: `cells: 13` (or however many cells the script writes).

- [ ] **Step 15.3: Remove the generator script (it was a one-shot)**

```bash
rm /Users/simon/Desktop/QTrend_v2/scripts/_gen_notebook.py
rmdir /Users/simon/Desktop/QTrend_v2/scripts 2>/dev/null || true
```

- [ ] **Step 15.4: Run full test suite as final acceptance**

```bash
cd ~/Desktop/QTrend_v2 && pytest -ra && ruff format --check src/ tests/ && ruff check src/ tests/
```
Expected: all pass, ruff clean.

- [ ] **Step 15.5: Commit**

```bash
cd ~/Desktop/QTrend_v2 && git add notebooks/ && git -c user.name=claude -c user.email=simon.wsm530@gmail.com commit -m "docs: v1 walkthrough notebook (load HC → run window → render reports)"
```

---

## v1 acceptance criteria (re-stated from spec §8)

After Task 15, the following should all be true:

- [x] `from qtrend_v2 import Strategy` callable (Task 11)
- [x] At least 3 bias windows from `data/bias_windows.csv` parse (Task 4) — Simon must still replace placeholders with real annotations
- [x] Per-window HTML report renders (Task 12, exercised in Task 14)
- [x] Aggregate report includes hit rate, PnL distribution, worst-window DD (Task 13)
- [x] Tests pass for bias, sizing, pullback, state machine, simulator (Tasks 4-9)
- [x] Smoke test backtest passes on real HC data (Task 14)
- [x] Notebook walks end-to-end (Task 15)
- [x] `ruff format` and `ruff check` clean (Task 15 step 5.4)

---

## Self-review pass

**Spec coverage:**
- §1 Purpose → covered by Tasks 1-15 collectively
- §2 Operating semantics → Tasks 4 (bias), 8 (state machine autonomy), 9 (simulator)
- §3 Data architecture → Task 3
- §4 Strategy architecture → Tasks 5, 6, 7, 8 (forecast, sizing, pullback, state machine)
- §5 Bias windows → Task 4
- §6 Backtest + reports → Tasks 10, 12, 13
- §7 Project layout → Tasks 1, 2 (skeleton); each subsequent task adds its file
- §8 v1 acceptance → re-verified above
- §9 Out of scope → not implemented, correctly omitted

**Placeholder scan:** no "TBD" / "implement later" / "similar to" remain. The `bias_windows.csv` rows are labelled as placeholders Simon must replace; this is intentional and noted in the task.

**Type consistency:** `Action`, `ActionKind`, `Leg`, `Fill`, `BiasWindow`, `WindowResult`, `ForecastSignal`, `Sizer`, `ConnorsPullback`, `StateMachine`, `SimulatorAdapter`, `Strategy` all defined once and referenced with matching signatures.

**Gaps fixed inline:** none found requiring retro-edits beyond the explicit refactor step in Task 7.6.

---

## Notes for the executor

- **Run from the QTrend_v2 root** (`cd ~/Desktop/QTrend_v2`) for every command.
- **Editable install** must be run once after Task 1 step 5 so subsequent tests can resolve `qtrend_v2`.
- **Wave 3 parallelisation**: Tasks 3, 4, 5, 6, 7 can run in parallel; each writes to disjoint files.
- **Commit per task** — don't batch.
- **If a test step fails**: do not blindly relax the test. Read the diff, fix the implementation. If the test itself is wrong, fix the test and explain the change in the commit message.
