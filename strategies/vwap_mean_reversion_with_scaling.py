import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from api.models import VwapMeanReversionWithScalingParams
from calculations.vwap import LiveVwap
from core import Tick
from strategies.vwap_mean_reversion import BandAttempt

from .handlers import vwap_mean_reversion_with_scaling_handler


class VwapMeanReversionWithScaling:
    """
    VWAP mean reversion with scale-in and trailing stop.

    Flow:
      1. Price breaches entry_std_dev band -> enter 1 contract immediately.
      2. Start a BandAttempt for delta confirmation.
      3. If confirmed AND trade is green -> add 1 contract, set trailing
         stop at entry1 price (breakeven protection).
      4. If confirmed but NOT green -> wait until green, then scale in.
      5. Trailing stop follows price by trail_ticks once active.

    Exits (checked in priority order):
      - Hard stop (risk_ticks from entry1) -> exit all contracts.
      - Trailing stop (if active) -> exit all contracts.
      - Price crosses VWAP -> exit all contracts (take profit).
    """

    def __init__(
        self,
        logger: logging.Logger,
        candles: List[Dict[str, Any]],
        params: VwapMeanReversionWithScalingParams,
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
        self.cooldown_seconds = params.cooldown_seconds

        # Trailing stop
        self.trail_ticks = params.trail_ticks

        # Scale-in confirmation
        self.attempt_seconds = params.attempt_seconds
        self.delta_ratio_threshold = params.delta_ratio_threshold
        self.min_response_ticks = params.min_response_ticks
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
        """
        Check for initial entry at band breach. No confirmation needed.
        Also starts the BandAttempt for potential scale-in.
        """
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

        if self._cooldown_until is not None and tick.t < self._cooldown_until:
            return None

        distance_std = (tick.price - vwap_val) / std_dev
        abs_distance = abs(distance_std)

        if abs_distance > self.max_std_dev:
            return None

        if abs_distance < self.entry_std_dev:
            return None

        direction = "SHORT" if distance_std > 0 else "LONG"

        if self._paused_direction == direction:
            return None

        entry = tick.price

        if direction == "LONG":
            stop_loss = round(entry - self.risk_ticks * self.tick_size, self.precision)
        else:
            stop_loss = round(entry + self.risk_ticks * self.tick_size, self.precision)

        self._cooldown_until = tick.t + timedelta(seconds=self.cooldown_seconds)

        # Start confirmation attempt for scale-in
        self.attempt = BandAttempt(
            direction=direction,
            start_t=tick.t,
            expire_t=tick.t + timedelta(seconds=self.attempt_seconds),
            start_price=tick.price,
            min_price=tick.price,
            max_price=tick.price,
            last_price=tick.price,
            tick_size=self.tick_size,
            absorption_ticks=self.absorption_ticks,
        )
        self.attempt.on_tick(tick.t, tick.price, tick.delta(), tick.size)

        self.logger.info(
            f"{direction} VWAP-MR entry at {entry} "
            f"vwap={vwap_val:.{self.precision}f} distance={abs_distance:.2f}std "
            f"(scale attempt started, {self.attempt_seconds}s window)",
        )

        return {
            "timestamp": timestamp,
            "direction": direction,
            "entry": entry,
            "take_profit": None,
            "stop_loss": stop_loss,
        }

    def check_scale(self, tick: Tick) -> bool:
        """
        Called by handler on each tick while in position and not yet scaled.
        Updates the attempt and returns True if scale-in is confirmed.
        """
        if self.attempt is None:
            return False

        if self.attempt.is_expired(tick.t):
            self.logger.debug("Scale attempt expired without confirmation")
            self.attempt = None
            return False

        delta = tick.delta()
        self.attempt.on_tick(tick.t, tick.price, delta, tick.size)

        if self._scale_confirmed(self.attempt):
            self.logger.info(
                f"Scale-in confirmed: dr={self.attempt.delta_ratio():.3f} "
                f"vol={self.attempt.sum_volume} absorbed={self.attempt.absorbed_volume}"
            )
            self.attempt = None
            return True

        return False

    def _scale_confirmed(self, attempt: BandAttempt) -> bool:
        if attempt.sum_volume < self.min_attempt_volume:
            return False

        dr = attempt.delta_ratio()
        if attempt.direction == "LONG":
            if dr < self.delta_ratio_threshold:
                return False
        else:
            if dr > -self.delta_ratio_threshold:
                return False

        min_resp = self.min_response_ticks * self.tick_size
        if attempt.direction == "LONG":
            if (attempt.last_price - attempt.min_price) < min_resp:
                return False
        else:
            if (attempt.max_price - attempt.last_price) < min_resp:
                return False

        if self.min_absorbed_volume > 0:
            if attempt.absorbed_volume < self.min_absorbed_volume:
                return False

        return True

    def on_stop_loss(self, direction: str) -> None:
        self._paused_direction = direction
        self.attempt = None

    def on_vwap_touch(self) -> None:
        self._paused_direction = None

    def reset(self) -> None:
        self.attempt = None
        self._cooldown_until = None
        self._paused_direction = None

    def get_handler(self) -> Callable:
        return vwap_mean_reversion_with_scaling_handler

    def __repr__(self) -> str:
        return (
            f"VwapMeanReversionWithScaling(vwap={self.vwap.vwap:.4f}, "
            f"std={self.vwap.std_dev:.4f}, "
            f"entry_std={self.entry_std_dev}, trail={self.trail_ticks})"
        )
