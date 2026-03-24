from datetime import datetime
from typing import Any, Dict, List, Optional

from core import Tick


def _floor_min(dt: datetime, minute_interval: int = 5) -> datetime:
    m = dt.minute - (dt.minute % minute_interval)
    return dt.replace(minute=m, second=0, microsecond=0)


class LiveEma:
    """
    An EMA calculator that:
      1. Seeds its initial value from historical candle close prices.
      2. Builds new candles on the fly from incoming ticks and updates
         the EMA each time a candle closes.

    This gives a continuous, up-to-date EMA throughout a backtest
    (or eventually a live session).
    """

    def __init__(
        self,
        period: int,
        candle_length_minutes: int,
        seed_candles: List[Dict[str, Any]],
    ) -> None:
        self.period = period
        self.k = 2.0 / (period + 1)
        self.candle_length = candle_length_minutes

        # Seed the EMA from historical candle closes
        closes = [c["c"] for c in seed_candles]
        if not closes:
            raise ValueError("Cannot seed EMA: no historical candles provided")

        if len(closes) >= period:
            # Standard approach: SMA over the first `period` closes, then EMA from there
            sma = sum(closes[:period]) / period
            ema = sma
            for c in closes[period:]:
                ema = c * self.k + ema * (1 - self.k)
            self._ema = ema
        else:
            # Not enough history for a full SMA; use whatever we have
            self._ema = sum(closes) / len(closes)

        # State for building the current candle from ticks
        self._current_bucket: Optional[datetime] = None
        self._current_candle: Optional[Dict[str, float]] = None

    @property
    def value(self) -> float:
        return self._ema

    def on_tick(self, tick: Tick) -> None:
        """
        Feed a tick into the live candle builder.
        When the time bucket rolls over, the completed candle's close
        updates the EMA before the new candle begins.
        """
        bucket = _floor_min(tick.t, self.candle_length)

        if self._current_bucket is None:
            # First tick: start the first live candle
            self._current_bucket = bucket
            self._current_candle = {
                "o": tick.price,
                "h": tick.price,
                "l": tick.price,
                "c": tick.price,
            }
            return

        if bucket != self._current_bucket:
            # New time bucket — close the previous candle and update EMA
            assert self._current_candle is not None
            close = self._current_candle["c"]
            self._ema = close * self.k + self._ema * (1 - self.k)

            # Start a fresh candle
            self._current_bucket = bucket
            self._current_candle = {
                "o": tick.price,
                "h": tick.price,
                "l": tick.price,
                "c": tick.price,
            }
        else:
            # Same bucket — update the in-progress candle
            assert self._current_candle is not None
            if tick.price > self._current_candle["h"]:
                self._current_candle["h"] = tick.price
            if tick.price < self._current_candle["l"]:
                self._current_candle["l"] = tick.price
            self._current_candle["c"] = tick.price
