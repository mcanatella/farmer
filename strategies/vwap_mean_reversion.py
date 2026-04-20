import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
 
from calculations.vwap import LiveVwap
from core import Tick
from api.models import VwapMeanReversionParams
 
 
@dataclass
class BandAttempt:
    """
    A localized "touch attempt" when price has breached a VWAP band.
    Accumulates orderflow and tracks price excursion during the attempt window.
    """
 
    direction: str  # "LONG" or "SHORT"
    start_t: datetime
    expire_t: datetime
    start_price: float
 
    min_price: float  # worst excursion during the attempt
    max_price: float
 
    sum_delta: int = 0
    sum_volume: int = 0
    last_price: float = 0.0
 
    def on_tick(self, t: datetime, price: float, delta: int, size: int) -> None:
        self.last_price = price
        if price < self.min_price:
            self.min_price = price
        if price > self.max_price:
            self.max_price = price
        self.sum_delta += delta
        self.sum_volume += size
 
    def delta_ratio(self) -> float:
        if self.sum_volume <= 0:
            return 0.0
        return self.sum_delta / self.sum_volume
 
    def is_expired(self, now: datetime) -> bool:
        return now >= self.expire_t
 
 
class VwapMeanReversion:
    """
    VWAP-based mean reversion strategy for highly liquid instruments (ES/MES).
 
    Thesis: price tends to revert to VWAP after extended moves. When price
    is statistically extended beyond a standard deviation band, enter in
    the direction back toward VWAP.
 
    Entry is confirmed via delta orderflow (the ZoneAttempt pattern):
      1. Price breaches `entry_std_dev` band → start an attempt.
      2. During the attempt window, accumulate delta and track excursion.
      3. Enter only when delta confirms reversal direction AND price has
         bounced from the worst excursion by `min_response_ticks`.
      4. Abandon the attempt if it expires without confirming.
 
    Take profit: dynamic — handler exits when price crosses VWAP.
    Stop loss: fixed `risk_ticks` beyond entry, away from VWAP.
 
    Safety:
      - `max_std_dev` skips entries when price is too far from VWAP
        (parabolic move / falling knife).
      - `min_session_volume` prevents trading before VWAP has stabilized,
        which matters when starting mid-session in live trading.
      - `cooldown_seconds` prevents rapid re-entry after a trade.
    """
 
    def __init__(
        self,
        logger: logging.Logger,
        candles: List[Dict[str, Any]],
        params: VwapMeanReversionParams,
    ) -> None:
        self.logger = logger
 
        # Core params
        self.tick_size = params.tick_size
        self.precision = params.precision
        self.entry_std_dev = params.entry_std_dev
        self.max_std_dev = params.max_std_dev
        self.risk_ticks = params.risk_ticks
        self.min_session_volume = params.min_session_volume
        self.min_std_dev = params.min_std_dev
 
        # Delta confirmation params
        self.use_delta_confirmation = params.use_delta_confirmation
        self.attempt_seconds = params.attempt_seconds
        self.delta_ratio_threshold = params.delta_ratio_threshold
        self.min_response_ticks = params.min_response_ticks
        self.cooldown_seconds = params.cooldown_seconds
 
        # VWAP with session reset (candles parameter is unused — VWAP is session-scoped)
        self.vwap = LiveVwap(
            session_reset_hour=params.session_reset_hour,
            session_reset_minute=params.session_reset_minute,
        )
 
        # State
        self.attempt: Optional[BandAttempt] = None
        self._cooldown_until: Optional[datetime] = None
        self._paused_direction: Optional[str] = None
 
    def check(
        self, tick: Tick, timestamp: Any = None, **kwargs: Any
    ) -> Dict[str, Any] | None:
        vwap_val = kwargs.get("vwap")
        std_dev = kwargs.get("std_dev")
        session_volume = kwargs.get("session_volume", 0)
 
        if vwap_val is None or std_dev is None:
            return None
 
        # Wait for VWAP to stabilize
        if session_volume < self.min_session_volume:
            return None
 
        # Bands haven't formed yet
        if std_dev <= 0:
            return None
        
        # Wait for bands to diverge sufficiently
        if self.min_std_dev is not None and std_dev < self.min_std_dev:
            return None
 
        now = tick.t
        delta = tick.delta()
 
        # --- (A) If an attempt is active, update it ---
        if self.attempt is not None:
            if self.attempt.is_expired(now):
                self.logger.debug("Attempt expired without confirmation")
                self.attempt = None
            else:
                self.attempt.on_tick(now, tick.price, delta, tick.size)
                if self._attempt_confirmed(self.attempt):
                    return self._confirm_entry(self.attempt, tick, vwap_val, timestamp)
                return None
 
        # --- (B) Cooldown ---
        if self._cooldown_until is not None and now < self._cooldown_until:
            return None
 
        # --- (C) Check for band breach ---
        # Distance from VWAP in standard deviations
        distance_std = (tick.price - vwap_val) / std_dev
        abs_distance = abs(distance_std)
 
        # Safety cap: skip parabolic moves
        if abs_distance > self.max_std_dev:
            return None
 
        # Must be beyond entry band
        if abs_distance < self.entry_std_dev:
            return None
 
        direction = "SHORT" if distance_std > 0 else "LONG"

        # Direction may be paused if we have already made a recent trade in that direction
        # and want to avoid immediate re-entry.
        if self._paused_direction == direction:
            return None
 
        # --- (D) Direct entry path (no delta confirmation) ---
        if not self.use_delta_confirmation:
            return self._direct_entry(tick, direction, vwap_val, std_dev, timestamp)
 
        # --- (E) Start a delta-confirmation attempt ---
        self.attempt = BandAttempt(
            direction=direction,
            start_t=now,
            expire_t=now + timedelta(seconds=self.attempt_seconds),
            start_price=tick.price,
            min_price=tick.price,
            max_price=tick.price,
            last_price=tick.price,
        )
        self.attempt.on_tick(now, tick.price, delta, tick.size)
 
        self.logger.debug(
            f"Attempt started: {direction} @ {tick.price} "
            f"vwap={vwap_val:.{self.precision}f} "
            f"distance={abs_distance:.2f}std expires_in={self.attempt_seconds}s"
        )
 
        return None
    
    def on_stop_loss(self, direction: str) -> None:
        self._paused_direction = direction

    def on_vwap_touch(self) -> None:
        """
        Handler calls this when price crosses VWAP, clearing any directional pause.
        """
        self._paused_direction = None
 
    def _attempt_confirmed(self, attempt: BandAttempt) -> bool:
        """
        Confirmation requires both:
          1. Delta imbalance in the expected reversion direction.
          2. Price has visibly bounced from the worst excursion.
        """
        dr = attempt.delta_ratio()
        min_resp = self.min_response_ticks * self.tick_size
 
        if attempt.direction == "LONG":
            # Need positive delta (buyers stepping in)
            if dr < self.delta_ratio_threshold:
                return False
            # Need bounce from min_price
            if (attempt.last_price - attempt.min_price) < min_resp:
                return False
        else:  # SHORT
            if dr > -self.delta_ratio_threshold:
                return False
            if (attempt.max_price - attempt.last_price) < min_resp:
                return False
 
        return True
 
    def _confirm_entry(
        self,
        attempt: BandAttempt,
        tick: Tick,
        vwap_val: float,
        timestamp: Any,
    ) -> Dict[str, Any]:
        direction = attempt.direction
        entry = tick.price
 
        if direction == "LONG":
            stop_loss = round(entry - self.risk_ticks * self.tick_size, self.precision)
        else:
            stop_loss = round(entry + self.risk_ticks * self.tick_size, self.precision)
 
        self._cooldown_until = tick.t + timedelta(seconds=self.cooldown_seconds)
        dr = attempt.delta_ratio()
        self.attempt = None
 
        self.logger.info(
            f"{direction} VWAP-MR CONFIRMED at {entry} "
            f"vwap={vwap_val:.{self.precision}f} "
            f"dr={dr:.3f} sum_vol={attempt.sum_volume}",
        )
 
        return {
            "timestamp": timestamp,
            "direction": direction,
            "entry": entry,
            "take_profit": None,  # dynamic — handler targets VWAP
            "stop_loss": stop_loss,
        }
 
    def _direct_entry(
        self,
        tick: Tick,
        direction: str,
        vwap_val: float,
        std_dev: float,
        timestamp: Any,
    ) -> Dict[str, Any]:
        entry = tick.price
 
        if direction == "LONG":
            stop_loss = round(entry - self.risk_ticks * self.tick_size, self.precision)
        else:
            stop_loss = round(entry + self.risk_ticks * self.tick_size, self.precision)
 
        self._cooldown_until = tick.t + timedelta(seconds=self.cooldown_seconds)
 
        abs_distance = abs((tick.price - vwap_val) / std_dev)
        self.logger.info(
            f"{direction} VWAP-MR signal (no delta) at {entry} "
            f"vwap={vwap_val:.{self.precision}f} distance={abs_distance:.2f}std",
        )
 
        return {
            "timestamp": timestamp,
            "direction": direction,
            "entry": entry,
            "take_profit": None,
            "stop_loss": stop_loss,
        }
 
    def reset(self) -> None:
        self.attempt = None
        self._cooldown_until = None
 
    def __repr__(self) -> str:
        return (
            f"VwapMeanReversion(vwap={self.vwap.vwap:.4f}, "
            f"std={self.vwap.std_dev:.4f}, "
            f"entry_std={self.entry_std_dev}, risk_ticks={self.risk_ticks})"
        )
