import logging
from typing import Any, Dict
from zoneinfo import ZoneInfo

from colorama import Fore

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


def vwap_mean_reversion_with_scaling_handler(
    tick: Tick, logger: logging.Logger, state: Dict[str, Any]
) -> None:
    strategy = state["strategy"]

    # Handler owns the VWAP update
    strategy.vwap.on_tick(tick)
    vwap_now = strategy.vwap.vwap

    tick_size = state["tick_size"]
    tick_value = state["tick_value"]

    # VWAP crossing detection — clear directional pause
    prev_price = state.get("prev_price")
    if prev_price is not None and vwap_now > 0:
        if (prev_price - vwap_now) * (tick.price - vwap_now) <= 0:
            strategy.on_vwap_touch()
    state["prev_price"] = tick.price

    position = state["position"]

    # --- No position: check for initial entry ---
    if position is None:
        signal = strategy.check(
            tick,
            tick.t,
            vwap=vwap_now,
            std_dev=strategy.vwap.std_dev,
            session_volume=strategy.vwap.session_volume,
        )
        if signal is not None:
            state["position"] = {
                "direction": signal["direction"],
                "timestamp": signal["timestamp"],
                "entry1": signal["entry"],
                "entry2": None,
                "stop_loss": signal["stop_loss"],
                "trailing_stop": None,
                "scaled": False,
                "confirmed": False,
                "waiting_for_green": False,
                "num_contracts": 1,
            }
        return

    direction = position["direction"]

    # --- Scale-in logic (only while not yet scaled) ---
    if not position["scaled"]:
        if not position["confirmed"]:
            confirmed = strategy.check_scale(tick)
            if confirmed:
                position["confirmed"] = True

                if direction == "LONG":
                    is_green = tick.price > position["entry1"]
                else:
                    is_green = tick.price < position["entry1"]

                if is_green:
                    _do_scale_in(position, tick, strategy, logger)
                    return
                else:
                    position["waiting_for_green"] = True

        elif position["waiting_for_green"]:
            if direction == "LONG":
                is_green = tick.price > position["entry1"]
            else:
                is_green = tick.price < position["entry1"]

            if is_green:
                _do_scale_in(position, tick, strategy, logger)
                return

    # --- Update trailing stop if active ---
    if position["trailing_stop"] is not None:
        trail_dist = strategy.trail_ticks * tick_size
        if direction == "LONG":
            new_stop = tick.price - trail_dist
            if new_stop > position["trailing_stop"]:
                position["trailing_stop"] = new_stop
        else:
            new_stop = tick.price + trail_dist
            if new_stop < position["trailing_stop"]:
                position["trailing_stop"] = new_stop

    # --- Exit checks (priority: hard stop > trailing stop > VWAP TP) ---
    exit_price = None
    exit_reason = None

    if direction == "LONG":
        if tick.price <= position["stop_loss"]:
            exit_price = position["stop_loss"]
            exit_reason = "hard_stop"
        elif (
            position["trailing_stop"] is not None
            and tick.price <= position["trailing_stop"]
        ):
            exit_price = position["trailing_stop"]
            exit_reason = "trailing_stop"
        elif tick.price >= vwap_now:
            exit_price = tick.price
            exit_reason = "vwap_tp"
    else:
        if tick.price >= position["stop_loss"]:
            exit_price = position["stop_loss"]
            exit_reason = "hard_stop"
        elif (
            position["trailing_stop"] is not None
            and tick.price >= position["trailing_stop"]
        ):
            exit_price = position["trailing_stop"]
            exit_reason = "trailing_stop"
        elif tick.price <= vwap_now:
            exit_price = tick.price
            exit_reason = "vwap_tp"

    if exit_price is None:
        return

    # --- PnL calculation ---
    total_pnl = 0.0

    # Contract 1
    if direction == "LONG":
        pnl1 = (exit_price - position["entry1"]) / tick_size * tick_value
    else:
        pnl1 = (position["entry1"] - exit_price) / tick_size * tick_value
    total_pnl += pnl1

    # Contract 2 (if scaled in)
    if position["scaled"] and position["entry2"] is not None:
        if direction == "LONG":
            pnl2 = (exit_price - position["entry2"]) / tick_size * tick_value
        else:
            pnl2 = (position["entry2"] - exit_price) / tick_size * tick_value
        total_pnl += pnl2

    total_pnl = round(total_pnl, 2)
    state["total_pnl"] += total_pnl

    if exit_reason == "hard_stop":
        strategy.on_stop_loss(direction)

    ts_start = (
        position["timestamp"]
        .replace(microsecond=0)
        .astimezone(ZoneInfo("America/Chicago"))
    )
    ts_end = tick.t.replace(microsecond=0).astimezone(ZoneInfo("America/Chicago"))

    contracts = position["num_contracts"]
    log_with_color(
        logger,
        f"Trade completed ({exit_reason}), Start = {ts_start}, End = {ts_end}, "
        f"PnL = ${total_pnl:.2f} ({contracts} contract{'s' if contracts > 1 else ''}), "
        f"VWAP = {vwap_now:.4f}",
        Fore.GREEN if total_pnl > 0 else Fore.RED,
        "info",
    )

    state["position"] = None


def _do_scale_in(
    position: Dict[str, Any],
    tick: Tick,
    strategy: Any,
    logger: logging.Logger,
) -> None:
    position["entry2"] = tick.price
    position["scaled"] = True
    position["num_contracts"] = 2
    position["waiting_for_green"] = False

    trail_dist = strategy.trail_ticks * strategy.tick_size

    if position["direction"] == "LONG":
        position["trailing_stop"] = position["entry1"] - trail_dist
    else:
        position["trailing_stop"] = position["entry1"] + trail_dist

    logger.info(
        f"Scaled in: +1 contract at {tick.price}, "
        f"trailing stop set at {position['trailing_stop']} "
        f"(trail_ticks={strategy.trail_ticks})",
    )
