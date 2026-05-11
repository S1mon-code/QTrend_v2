"""Forecast signals (plug-in)."""

from qtrend_v2.forecast.base import ForecastSignal
from qtrend_v2.forecast.ewmac import EWMAC

__all__ = ["ForecastSignal", "EWMAC"]
