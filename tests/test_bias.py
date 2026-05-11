"""Tests for BiasWindow + BiasWindowLoader."""

from __future__ import annotations

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
    assert isinstance(windows[0], BiasWindow)
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
