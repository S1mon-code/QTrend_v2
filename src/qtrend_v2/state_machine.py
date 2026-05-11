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
        self._pending_delta: int = 0
        self._pending_age_bars: int = 0

    @property
    def current_lots(self) -> int:
        return sum(leg.lots for leg in self._legs)

    def reset(self) -> None:
        self._legs.clear()
        self._peak_close = None
        self._pending_delta = 0
        self._pending_age_bars = 0

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
        # 1. Trailing stop check.
        if self.current_lots > 0:
            if self._peak_close is None or close > self._peak_close:
                self._peak_close = close
            stop_level = self._peak_close - self.atr_multiplier * atr
            if close <= stop_level:
                self._end_round()
                return Action(kind=ActionKind.FLAT_ALL, lots=0, reason="trailing_stop")

        # 2. Desired delta.
        delta = target_lots - self.current_lots

        # 3. At target — clear pending state, HOLD.
        if delta == 0:
            self._pending_delta = 0
            self._pending_age_bars = 0
            return Action(kind=ActionKind.HOLD, lots=0, reason="at_target")

        # 4. Pending state housekeeping (handles direction flip and refresh).
        if (delta > 0 and self._pending_delta < 0) or (delta < 0 and self._pending_delta > 0):
            self._pending_delta = delta
            self._pending_age_bars = 0
        elif self._pending_delta == 0:
            self._pending_delta = delta
            self._pending_age_bars = 0
        else:
            self._pending_delta = delta

        # 5. Timing filter (1H RSI).
        timing_ok = (delta > 0 and rsi2 < self.buy_rsi_max) or (
            delta < 0 and rsi2 >= self.sell_rsi_min
        )
        if not timing_ok and self._pending_age_bars + 1 < self.timing_K_bars:
            self._pending_age_bars += 1
            return Action(kind=ActionKind.HOLD, lots=0, reason="timing_deferred")

        # 6. Fire.
        if delta > 0:
            return Action(kind=ActionKind.BUY, lots=delta, reason="enter_or_scale_up")
        else:
            return Action(kind=ActionKind.SELL, lots=-delta, reason="scale_down")

    def force_flat(self, *, timestamp: pd.Timestamp, reason: str) -> Action:
        if self.current_lots == 0:
            return Action(kind=ActionKind.HOLD, lots=0, reason=f"flat_already:{reason}")
        self._end_round()
        return Action(kind=ActionKind.FLAT_ALL, lots=0, reason=reason)

    def record_fill(
        self,
        *,
        timestamp: pd.Timestamp,
        kind: ActionKind,
        lots: int,
        price: float,
    ) -> None:
        """Reconcile state after ExecutionAdapter reports a fill."""
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
        if self._pending_delta == 0:
            self._pending_age_bars = 0

    def _reduce_legs(self, lots_to_sell: int) -> None:
        """FIFO: oldest legs sold first."""
        remaining = lots_to_sell
        new_legs: list[Leg] = []
        for leg in self._legs:
            if remaining >= leg.lots:
                remaining -= leg.lots
                continue
            if remaining > 0:
                new_legs.append(
                    Leg(timestamp=leg.timestamp, price=leg.price, lots=leg.lots - remaining)
                )
                remaining = 0
            else:
                new_legs.append(leg)
        self._legs = new_legs

    def _end_round(self) -> None:
        self._legs.clear()
        self._peak_close = None
        self._pending_delta = 0
        self._pending_age_bars = 0
