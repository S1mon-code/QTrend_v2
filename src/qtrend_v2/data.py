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
