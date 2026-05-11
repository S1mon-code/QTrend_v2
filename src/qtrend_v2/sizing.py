"""Forecast → integer-lot sizing with deadband hysteresis."""

from __future__ import annotations

RISING_THRESHOLDS = (4.0, 8.0, 12.0, 16.0, 20.0)
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
        forecast = max(0.0, min(forecast, 100.0))

        natural = 0
        for i, t in enumerate(RISING_THRESHOLDS):
            if forecast >= t:
                natural = i + 1
        natural = min(natural, MAX_LOTS)

        if natural >= self._last_lots:
            new_lots = natural
        else:
            new_lots = self._last_lots
            while new_lots > 0 and forecast <= FALLING_THRESHOLDS[new_lots - 1]:
                new_lots -= 1
            new_lots = max(new_lots, natural)

        self._last_lots = new_lots
        return new_lots

    def reset(self) -> None:
        self._last_lots = 0
