import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from calculations import LiveEma
from core import Tick
from models import StrategyParams


class MeanReversionEma:
    """
    Mean-reversion strategy based on the Exponential Moving Average (EMA).

    Thesis: price tends to snap back to the EMA after extended moves away.
    When price drifts far enough from the EMA, this strategy enters in the
    direction back toward it.

    Entry:
        - Price is at least `entry_distance_ticks` away from the EMA.
        - Price above EMA → SHORT (expect reversion down).
        - Price below EMA → LONG  (expect reversion up).

    Take profit:
        - Default (`target_ema=True`): TP is set at the EMA level at entry time.
        - Alternative: fixed `reward_ticks` offset from entry.

    Stop loss:
        - Fixed `risk_ticks` beyond entry, away from the EMA.

    Safety:
        - `max_distance_ticks` prevents entries when price is too far away
          (falling knife / parabolic move — probably not a mean-reversion setup).
        - `cooldown_seconds` prevents rapid re-entry after a trade.
    """

    def __init__(
        self,
        logger: logging.Logger,
        candles: List[Dict[str, Any]],
        params: StrategyParams,
    ) -> None:
        if params.kind != "mean_reversion_ema":
            raise ValueError(f"Invalid strategy_params kind: {params.kind}")

        self.logger = logger

        # Core params
        self.tick_size = params.tick_size
        self.precision = params.precision
        self.entry_distance_ticks = params.entry_distance_ticks
        self.max_distance_ticks = params.max_distance_ticks
        self.reward_ticks = params.reward_ticks
        self.risk_ticks = params.risk_ticks
        self.target_ema = params.target_ema
        self.cooldown_seconds = params.cooldown_seconds

        # Build the live EMA, seeded from historical candles
        self.ema = LiveEma(
            period=params.ema_period,
            candle_length_minutes=params.candle_length,
            seed_candles=candles,
        )

        # Cooldown tracking
        self._cooldown_until: Optional[datetime] = None

    def check(
        self, tick: Tick, timestamp: Any = None, **kwargs: Any
    ) -> Dict[str, Any] | None:
        ema_val = kwargs.get("ema")
        if ema_val is None:
            return None

        if self._cooldown_until is not None and tick.t < self._cooldown_until:
            return None

        distance_ticks = (tick.price - ema_val) / self.tick_size
        abs_distance = abs(distance_ticks)

        if abs_distance < self.entry_distance_ticks:
            return None

        if (
            self.max_distance_ticks is not None
            and abs_distance > self.max_distance_ticks
        ):
            return None

        direction = "SHORT" if distance_ticks > 0 else "LONG"
        entry = tick.price

        if direction == "LONG":
            stop_loss = round(entry - self.risk_ticks * self.tick_size, self.precision)
        else:
            stop_loss = round(entry + self.risk_ticks * self.tick_size, self.precision)

        self._cooldown_until = tick.t + timedelta(seconds=self.cooldown_seconds)

        self.logger.info(
            f"{direction} mean-reversion signal: entry={entry} "
            f"ema={ema_val:.{self.precision}f} distance={abs_distance:.1f} ticks",
        )

        return {
            "timestamp": timestamp,
            "direction": direction,
            "entry": entry,
            "take_profit": None,
            "stop_loss": stop_loss,
        }

    def reset(self) -> None:
        self._cooldown_until = None

    def __repr__(self) -> str:
        return (
            f"MeanReversionEma(ema={self.ema.value:.4f}, "
            f"entry_dist={self.entry_distance_ticks}, "
            f"risk={self.risk_ticks}, target_ema={self.target_ema})"
        )
