from datetime import datetime
from typing import Any, Dict, List, Optional
 
from core import Tick
 
 
def _floor_min(dt: datetime, minute_interval: int = 5) -> datetime:
    m = dt.minute - (dt.minute % minute_interval)
    return dt.replace(minute=m, second=0, microsecond=0)
 
 
class LiveAtr:
    """
    A rolling Average True Range (ATR) calculator that:
      1. Seeds its initial value from historical candle data.
      2. Builds new candles on the fly from incoming ticks and updates
         the ATR each time a candle closes.
 
    ATR measures the average range of price movement per candle,
    which is a good proxy for realized volatility. High ATR means
    the market is moving a lot per candle — bad for mean reversion.
 
    True Range for a candle is defined as:
        max(high - low, abs(high - prev_close), abs(low - prev_close))
 
    ATR is a smoothed (EMA-style) average of True Range over `period` candles.
    """
 
    def __init__(
        self,
        period: int,
        candle_length_minutes: int,
        seed_candles: List[Dict[str, Any]],
    ) -> None:
        self.period = period
        self.candle_length = candle_length_minutes
 
        if len(seed_candles) < 2:
            raise ValueError("Cannot seed ATR: need at least 2 historical candles")
 
        # Compute true ranges from historical candles
        true_ranges: List[float] = []
        for i in range(1, len(seed_candles)):
            prev_close = seed_candles[i - 1]["c"]
            high = seed_candles[i]["h"]
            low = seed_candles[i]["l"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
 
        # Seed ATR: SMA over first `period` true ranges, then Wilder smooth from there
        if len(true_ranges) >= period:
            atr = sum(true_ranges[:period]) / period
            for tr in true_ranges[period:]:
                atr = (atr * (period - 1) + tr) / period
            self._atr = atr
        else:
            self._atr = sum(true_ranges) / len(true_ranges)
 
        # Track the previous candle's close for true range calculation
        self._prev_close: float = seed_candles[-1]["c"]
 
        # State for building the current candle from ticks
        self._current_bucket: Optional[datetime] = None
        self._current_candle: Optional[Dict[str, float]] = None
 
    @property
    def value(self) -> float:
        return self._atr
 
    def on_tick(self, tick: Tick) -> None:
        """
        Feed a tick into the live candle builder.
        When the time bucket rolls over, the completed candle's true range
        updates the ATR before the new candle begins.
        """
        bucket = _floor_min(tick.t, self.candle_length)
 
        if self._current_bucket is None:
            self._current_bucket = bucket
            self._current_candle = {
                "o": tick.price,
                "h": tick.price,
                "l": tick.price,
                "c": tick.price,
            }
            return
 
        if bucket != self._current_bucket:
            # New time bucket — close the previous candle and update ATR
            assert self._current_candle is not None
            high = self._current_candle["h"]
            low = self._current_candle["l"]
 
            tr = max(
                high - low,
                abs(high - self._prev_close),
                abs(low - self._prev_close),
            )
 
            # Wilder smoothing
            self._atr = (self._atr * (self.period - 1) + tr) / self.period
 
            # This candle's close becomes prev_close for the next candle
            self._prev_close = self._current_candle["c"]
 
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
