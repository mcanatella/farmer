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

    # Handler owns the EMA update
    strategy.ema.on_tick(tick)

    if state["position"] is None:
        state["position"] = strategy.check(tick, tick.t, ema=strategy.ema.value)
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
