import logging
from typing import Any, Dict
from zoneinfo import ZoneInfo

from colorama import Fore

from calculations import DeltaEvent
from config import log_with_color
from core import Tick


def static_bounce_handler(
    tick: Tick, logger: logging.Logger, state: Dict[str, Any]
) -> None:
    """
    Handler for processing ticks in a StaticBounce backtest.
    Updates the state with PnL when a position is closed.
    """
    # Handle position
    if state["position"] is None:
        state["position"] = state["strategy"].check(tick, tick.t)
        if state["position"] is None:
            return

    tick_size = state["tick_size"]
    tick_value = state["tick_value"]
    market_price = state["position"]["entry"]

    price_diff = 0
    if state["position"]["direction"] == "LONG":
        if tick.price >= state["position"]["take_profit"]:
            price_diff = state["position"]["take_profit"] - market_price
        elif tick.price <= state["position"]["stop_loss"]:
            price_diff = state["position"]["stop_loss"] - market_price
        else:
            return
    else:
        if tick.price <= state["position"]["take_profit"]:
            price_diff = market_price - state["position"]["take_profit"]
        elif tick.price >= state["position"]["stop_loss"]:
            price_diff = market_price - state["position"]["stop_loss"]
        else:
            return

    ticks_moved = price_diff / tick_size
    profit_loss = round(ticks_moved * tick_value, 2)
    state["total_pnl"] += profit_loss

    ts_start = (
        state["position"]["timestamp"]
        .replace(microsecond=0)
        .astimezone(ZoneInfo("America/Chicago"))
    )
    ts_end = tick.t.replace(microsecond=0).astimezone(ZoneInfo("America/Chicago"))

    log_with_color(
        logger,
        f"Trade completed, Start = {ts_start}, End = {ts_end}, PnL = ${profit_loss:.2f}",
        Fore.GREEN if profit_loss > 0 else Fore.RED,
        "info",
    )

    # Reset position
    state["position"] = None


def mean_reversion_ema_handler(
    tick: Tick, logger: logging.Logger, state: Dict[str, Any]
) -> None:
    strategy = state["strategy"]

    # Handler owns the EMA and ATR updates
    strategy.ema.on_tick(tick)
    strategy.atr.on_tick(tick)

    if state["position"] is None:
        state["position"] = strategy.check(
            tick, tick.t, ema=strategy.ema.value, atr=strategy.atr.value
        )
        return

    tick_size = state["tick_size"]
    tick_value = state["tick_value"]
    market_price = state["position"]["entry"]
    ema_now = strategy.ema.value

    if state["position"]["direction"] == "LONG":
        if tick.price >= ema_now:
            price_diff = tick.price - market_price
        elif tick.price <= state["position"]["stop_loss"]:
            price_diff = state["position"]["stop_loss"] - market_price
        else:
            return
    else:
        if tick.price <= ema_now:
            price_diff = market_price - tick.price
        elif tick.price >= state["position"]["stop_loss"]:
            price_diff = market_price - state["position"]["stop_loss"]
        else:
            return

    ticks_moved = price_diff / tick_size
    profit_loss = round(ticks_moved * tick_value, 2)
    state["total_pnl"] += profit_loss

    ts_start = (
        state["position"]["timestamp"]
        .replace(microsecond=0)
        .astimezone(ZoneInfo("America/Chicago"))
    )
    ts_end = tick.t.replace(microsecond=0).astimezone(ZoneInfo("America/Chicago"))

    log_with_color(
        logger,
        f"Trade completed, Start = {ts_start}, End = {ts_end}, "
        f"PnL = ${profit_loss:.2f}, EMA at exit = {ema_now:.4f}",
        Fore.GREEN if profit_loss > 0 else Fore.RED,
        "info",
    )

    state["position"] = None


def vwap_mean_reversion_handler(
    tick: Tick, logger: logging.Logger, state: Dict[str, Any]
) -> None:
    strategy = state["strategy"]

    # Handler owns the VWAP update
    strategy.vwap.on_tick(tick)
    vwap_now = strategy.vwap.vwap

    # Track VWAP crossings to clear any directional pause.
    # Compare current price to previous price relative to VWAP — if they
    # straddle VWAP, a crossing occurred.
    prev_price = state.get("prev_price")
    if prev_price is not None and vwap_now > 0:
        crossed = (prev_price - vwap_now) * (tick.price - vwap_now) <= 0
        if crossed:
            strategy.on_vwap_touch()
    state["prev_price"] = tick.price

    if state["position"] is None:
        state["position"] = strategy.check(
            tick,
            tick.t,
            vwap=vwap_now,
            std_dev=strategy.vwap.std_dev,
            session_volume=strategy.vwap.session_volume,
        )
        return

    tick_size = state["tick_size"]
    tick_value = state["tick_value"]
    market_price = state["position"]["entry"]
    direction = state["position"]["direction"]
    stopped_out = False

    if direction == "LONG":
        if tick.price >= vwap_now:
            price_diff = tick.price - market_price
        elif tick.price <= state["position"]["stop_loss"]:
            price_diff = state["position"]["stop_loss"] - market_price
            stopped_out = True
        else:
            return
    else:
        if tick.price <= vwap_now:
            price_diff = market_price - tick.price
        elif tick.price >= state["position"]["stop_loss"]:
            price_diff = market_price - state["position"]["stop_loss"]
            stopped_out = True
        else:
            return

    ticks_moved = price_diff / tick_size
    profit_loss = round(ticks_moved * tick_value, 2)
    state["total_pnl"] += profit_loss

    # If this was a stop-out, pause that direction until price returns to VWAP
    if stopped_out:
        strategy.on_stop_loss(direction)

    ts_start = (
        state["position"]["timestamp"]
        .replace(microsecond=0)
        .astimezone(ZoneInfo("America/Chicago"))
    )
    ts_end = tick.t.replace(microsecond=0).astimezone(ZoneInfo("America/Chicago"))

    log_with_color(
        logger,
        f"Trade completed, Start = {ts_start}, End = {ts_end}, "
        f"PnL = ${profit_loss:.2f}, VWAP at exit = {vwap_now:.4f}",
        Fore.GREEN if profit_loss > 0 else Fore.RED,
        "info",
    )

    state["position"] = None
