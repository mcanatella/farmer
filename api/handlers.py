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

    market_price = state["position"]["entry"]
    profit_loss = 0
    if state["position"]["direction"] == "LONG":
        if tick.price >= state["position"]["take_profit"]:
            profit_loss = round(
                (state["position"]["take_profit"] - market_price) * 1000, 2
            )
        elif tick.price <= state["position"]["stop_loss"]:
            profit_loss = round(
                (state["position"]["stop_loss"] - market_price) * 1000, 2
            )
        else:
            return
    else:
        if tick.price <= state["position"]["take_profit"]:
            profit_loss = round(
                (market_price - state["position"]["take_profit"]) * 1000, 2
            )
        elif tick.price >= state["position"]["stop_loss"]:
            profit_loss = round(
                (market_price - state["position"]["stop_loss"]) * 1000, 2
            )
        else:
            return

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
