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
