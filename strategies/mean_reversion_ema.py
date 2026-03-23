import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
 
from calculations.ema import LiveEma
from core import Tick
from models import MeanReversionEmaParams


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
        params: MeanReversionEmaParams,
    ) -> None:
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
 
    def check(self, tick: Tick, timestamp: Any = None) -> Dict[str, Any] | None:
        # Always update the EMA with every tick so candles stay current
        self.ema.on_tick(tick)
 
        ema_val = self.ema.value
 
        # Cooldown check
        if self._cooldown_until is not None and tick.t < self._cooldown_until:
            return None
 
        # How far is price from the EMA, measured in ticks?
        distance_ticks = (tick.price - ema_val) / self.tick_size
 
        abs_distance = abs(distance_ticks)
 
        # Must be far enough to qualify as an entry
        if abs_distance < self.entry_distance_ticks:
            return None
 
        # Must not be too far (avoid catching a falling knife)
        if self.max_distance_ticks is not None and abs_distance > self.max_distance_ticks:
            return None
 
        # Mean reversion: trade back toward the EMA
        if distance_ticks > 0:
            direction = "SHORT"  # price above EMA → expect snap back down
        else:
            direction = "LONG"  # price below EMA → expect snap back up
 
        entry = tick.price
 
        # Take profit
        if self.target_ema:
            # Target the EMA itself (the whole thesis)
            take_profit = round(ema_val, self.precision)
        else:
            # Fixed tick offset
            if direction == "LONG":
                take_profit = round(
                    entry + self.reward_ticks * self.tick_size, self.precision
                )
            else:
                take_profit = round(
                    entry - self.reward_ticks * self.tick_size, self.precision
                )
 
        # Stop loss: fixed distance beyond entry, away from EMA
        if direction == "LONG":
            stop_loss = round(
                entry - self.risk_ticks * self.tick_size, self.precision
            )
        else:
            stop_loss = round(
                entry + self.risk_ticks * self.tick_size, self.precision
            )
 
        # Activate cooldown
        self._cooldown_until = tick.t + timedelta(seconds=self.cooldown_seconds)
 
        self.logger.info(
            f"{direction} mean-reversion signal: entry={entry} ema={ema_val:.{self.precision}f} "
            f"distance={abs_distance:.1f} ticks",
            extra={
                "timestamp": timestamp,
                "event": "signal_detected",
                "direction": direction,
                "entry": entry,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "ema_value": round(ema_val, self.precision),
                "distance_ticks": round(distance_ticks, 1),
            },
        )
 
        return {
            "timestamp": timestamp,
            "direction": direction,
            "entry": entry,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "level": round(ema_val, self.precision),
        }
 
    def reset(self) -> None:
        self._cooldown_until = None
 
    def __repr__(self) -> str:
        return (
            f"MeanReversionEma(ema={self.ema.value:.4f}, "
            f"entry_dist={self.entry_distance_ticks}, "
            f"risk={self.risk_ticks}, target_ema={self.target_ema})"
        )
