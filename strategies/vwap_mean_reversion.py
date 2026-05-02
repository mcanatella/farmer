import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable

from api.models import VwapMeanReversionParams
from calculations.vwap import LiveVwap
from core import Tick

from .handlers import vwap_mean_reversion_handler


@dataclass
class BandAttempt:
    """
    A localized attempt when price breaches a VWAP band.
    Accumulates orderflow, tracks excursion, and detects absorption.
    """

    direction: str
    start_t: datetime
    expire_t: datetime
    start_price: float

    min_price: float
    max_price: float

    tick_size: float
    absorption_ticks: int

    sum_delta: int = 0
    sum_volume: int = 0
    absorbed_volume: int = 0
    last_price: float = 0.0

    def on_tick(self, t: datetime, price: float, delta: int, size: int) -> None:
        self.last_price = price
        if price < self.min_price:
            self.min_price = price
        if price > self.max_price:
            self.max_price = price
        self.sum_delta += delta
        self.sum_volume += size

        threshold = self.absorption_ticks * self.tick_size

        if self.direction == "LONG" and delta < 0:
            if (self.start_price - price) < threshold:
                self.absorbed_volume += size
        elif self.direction == "SHORT" and delta > 0:
            if (price - self.start_price) < threshold:
                self.absorbed_volume += size

    def delta_ratio(self) -> float:
        if self.sum_volume <= 0:
            return 0.0
        return self.sum_delta / self.sum_volume

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expire_t


class VwapMeanReversion:
    """
    VWAP mean reversion with delta confirmation, absorption detection,
    and minimum attempt volume filtering.

    Entry flow:
      1. Price breaches entry_std_dev band -> start an attempt.
      2. Accumulate orderflow for attempt_seconds.
      3. Confirm only when ALL of:
         - Total attempt volume >= min_attempt_volume
         - Delta ratio exceeds threshold in expected direction
         - Price has bounced from worst excursion by min_response_ticks
         - Absorbed volume >= min_absorbed_volume (if enabled)
      4. Abandon if attempt expires without confirming.

    Take profit: dynamic — handler exits when price crosses VWAP.
    Stop loss: fixed risk_ticks beyond entry.
    """

    def __init__(
        self,
        logger: logging.Logger,
        candles: List[Dict[str, Any]],
        params: VwapMeanReversionParams,
    ) -> None:
        self.logger = logger

        # Core
        self.tick_size = params.tick_size
        self.precision = params.precision
        self.entry_std_dev = params.entry_std_dev
        self.max_std_dev = params.max_std_dev
        self.min_std_dev = params.min_std_dev
        self.risk_ticks = params.risk_ticks
        self.min_session_volume = params.min_session_volume

        # Delta confirmation
        self.attempt_seconds = params.attempt_seconds
        self.delta_ratio_threshold = params.delta_ratio_threshold
        self.min_response_ticks = params.min_response_ticks
        self.cooldown_seconds = params.cooldown_seconds

        # Volume and absorption filters
        self.min_attempt_volume = params.min_attempt_volume
        self.min_absorbed_volume = params.min_absorbed_volume
        self.absorption_ticks = params.absorption_ticks

        # VWAP (session-scoped, candles not used)
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

        if session_volume < self.min_session_volume:
            return None

        if std_dev <= 0:
            return None

        if self.min_std_dev is not None and std_dev < self.min_std_dev:
            return None

        now = tick.t
        delta = tick.delta()

        # --- Active attempt: update and check confirmation ---
        if self.attempt is not None:
            if self.attempt.is_expired(now):
                self.logger.debug("Attempt expired without confirmation")
                self.attempt = None
            else:
                self.attempt.on_tick(now, tick.price, delta, tick.size)
                if self._attempt_confirmed(self.attempt):
                    return self._enter(self.attempt, tick, vwap_val, timestamp, std_dev)
                return None

        # --- Cooldown ---
        if self._cooldown_until is not None and now < self._cooldown_until:
            return None

        # --- Band breach detection ---
        distance_std = (tick.price - vwap_val) / std_dev
        abs_distance = abs(distance_std)

        if abs_distance > self.max_std_dev:
            return None

        if abs_distance < self.entry_std_dev:
            return None

        direction = "SHORT" if distance_std > 0 else "LONG"

        # Directional pause: don't re-enter same side after stop-out
        if self._paused_direction == direction:
            return None

        # --- Start attempt ---
        self.attempt = BandAttempt(
            direction=direction,
            start_t=now,
            expire_t=now + timedelta(seconds=self.attempt_seconds),
            start_price=tick.price,
            min_price=tick.price,
            max_price=tick.price,
            last_price=tick.price,
            tick_size=self.tick_size,
            absorption_ticks=self.absorption_ticks,
        )
        self.attempt.on_tick(now, tick.price, delta, tick.size)

        self.logger.debug(
            f"Attempt started: {direction} @ {tick.price} "
            f"vwap={vwap_val:.{self.precision}f} "
            f"distance={abs_distance:.2f}std"
        )

        return None

    def _attempt_confirmed(self, attempt: BandAttempt) -> bool:
        # 1. Minimum volume — reject noise
        if attempt.sum_volume < self.min_attempt_volume:
            return False

        # 2. Delta ratio in expected direction
        dr = attempt.delta_ratio()
        if attempt.direction == "LONG":
            if dr < self.delta_ratio_threshold:
                return False
        else:
            if dr > -self.delta_ratio_threshold:
                return False

        # 3. Price response — visible bounce from worst excursion
        min_resp = self.min_response_ticks * self.tick_size
        if attempt.direction == "LONG":
            if (attempt.last_price - attempt.min_price) < min_resp:
                return False
        else:
            if (attempt.max_price - attempt.last_price) < min_resp:
                return False

        # 4. Absorption — passive defense of the level
        if self.min_absorbed_volume > 0:
            if attempt.absorbed_volume < self.min_absorbed_volume:
                return False

        return True

    def _enter(
        self,
        attempt: BandAttempt,
        tick: Tick,
        vwap_val: float,
        timestamp: Any,
        std_dev: float,
    ) -> Dict[str, Any]:
        direction = attempt.direction
        entry = tick.price

        if direction == "LONG":
            stop_loss = round(entry - self.risk_ticks * self.tick_size, self.precision)
        else:
            stop_loss = round(entry + self.risk_ticks * self.tick_size, self.precision)

        self._cooldown_until = tick.t + timedelta(seconds=self.cooldown_seconds)
        dr = attempt.delta_ratio()

        self.logger.info(
            f"{direction} VWAP-MR CONFIRMED at {entry} "
            f"vwap={vwap_val:.{self.precision}f} "
            f"dr={dr:.3f} vol={attempt.sum_volume} absorbed={attempt.absorbed_volume} std={std_dev:.2f}",
        )

        self.attempt = None

        return {
            "timestamp": timestamp,
            "direction": direction,
            "entry": entry,
            "take_profit": None,
            "stop_loss": stop_loss,
        }

    def on_stop_loss(self, direction: str) -> None:
        self._paused_direction = direction

    def on_vwap_touch(self) -> None:
        self._paused_direction = None

    def reset(self) -> None:
        self.attempt = None
        self._cooldown_until = None
        self._paused_direction = None

    def get_handler(self) -> Callable:
        return vwap_mean_reversion_handler

    def __repr__(self) -> str:
        return (
            f"VwapMeanReversion(vwap={self.vwap.vwap:.4f}, "
            f"std={self.vwap.std_dev:.4f}, "
            f"entry_std={self.entry_std_dev}, risk_ticks={self.risk_ticks})"
        )
