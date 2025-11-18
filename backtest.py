from calculators import CsvCalculator
from chart import Level, SignalDispatcher
from colorama import Fore, Style
from config import (
    BacktestSettings,
    DiscoverSettings,
    init_backtest_logger,
    log_with_color,
)
from core import Tick, EngineState, run_engine_async
from datetime import datetime, timedelta
from tickers import CsvTicker
from typing import Any, Dict
from zoneinfo import ZoneInfo

import argparse
import asyncio


async def main(args):
    logger = init_backtest_logger()

    # Parse string version of the back test date into a date object
    d = datetime.strptime(args.backtest_date, "%Y%m%d").date()

    # Subtract n days and 1 day to get the candlestick timeframe
    start_date = d - timedelta(days=args.days)
    end_date = d - timedelta(days=1)

    calculator = CsvCalculator(
        logger,
        "cl_historical",
        start_date,
        end_date,
        ["CLU5", "CLX5", "CLZ5"],  # TODO: Make this configurable
        candle_length=args.candle_length,
        unit=args.unit,
        price_tolerance=args.price_tolerance,
        min_separation=args.min_separation,
        top_n=args.top_n,
    )

    # Once the mock poller has candles populated, it can calculate support and resistance levels
    support_dict, resistance_dict = calculator.calculate_and_print()

    reward_points = 0.20
    risk_points = 0.10

    support = [
        Level(
            round(lvl["price"], 2),
            name=None,
            support=True,
            resistance=True,
            proximity_threshold=0.03,
            reward_points=reward_points,
            risk_points=risk_points,
        )
        for lvl in support_dict
    ]
    resistance = [
        Level(
            round(lvl["price"], 2),
            name=None,
            support=True,
            resistance=True,
            proximity_threshold=0.03,
            reward_points=reward_points,
            risk_points=risk_points,
        )
        for lvl in resistance_dict
    ]

    # The mock signal dispatcher will be used as we traverse tick data for a particular trading day
    mock_dispatcher = SignalDispatcher(logger, levels=(support + resistance))

    total_pnl: float = 0.00
    position: Dict[str, Any] = None

    # The handler will determine when to enter and exit trades similar to the signal dispatcher used in farm.py
    def handler(tick: Tick, state: Any):
        nonlocal logger, total_pnl, position, mock_dispatcher

        if position is None:
            position = mock_dispatcher.check(tick.price, tick.t)
            if position is None:
                return

        market_price = position["entry"]
        profit_loss = 0
        if position["direction"] == "LONG":
            if tick.price >= position["take_profit"]:
                profit_loss = round((position["take_profit"] - market_price) * 1000, 2)
            elif tick.price <= position["stop_loss"]:
                profit_loss = round((position["stop_loss"] - market_price) * 1000, 2)
            else:
                return
        else:
            if tick.price <= position["take_profit"]:
                profit_loss = round((market_price - position["take_profit"]) * 1000, 2)
            elif tick.price >= position["stop_loss"]:
                profit_loss = round((market_price - position["stop_loss"]) * 1000, 2)
            else:
                return

        total_pnl += profit_loss

        ts_start = (
            position["timestamp"]
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
        position = None

    state = EngineState()
    filename = f"{args.data_dir}/glbx-mdp3-{args.backtest_date}.trades.csv"
    ticker = CsvTicker(filename, ["CLU5", "CLX5", "CLZ5"])
    await run_engine_async(ticker, state, handler)

    log_with_color(
        logger,
        f"Total PnL on Day = ${total_pnl:.2f}{Style.RESET_ALL}",
        Fore.GREEN if total_pnl > 0 else Fore.RED,
        "info",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tunable support and resistance level finder"
    )
    BacktestSettings.set_args(parser)
    DiscoverSettings.set_args(parser)
    args = parser.parse_args()

    asyncio.run(main(args))
