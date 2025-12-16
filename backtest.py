from aggregators import CsvAggregator
from strategies import StaticBounce
from backtests.test_static_bounce import static_bounce_handler
from colorama import Fore, Style
from config import (
    BacktestSettings,
    init_backtest_logger,
    log_with_color,
)
from core import run_engine_async
from datetime import datetime, timedelta
from tickers import CsvTicker
from typing import Any, Dict

import argparse
import asyncio


async def main(args) -> None:
    settings = BacktestSettings.build(args)

    logger = init_backtest_logger()

    # Parse string version of the back test date into a date object
    d = datetime.strptime(settings.backtest_date, "%Y%m%d").date()

    # Subtract n days and 1 day to get the candlestick timeframe
    start_date = d - timedelta(days=settings.days)
    end_date = d - timedelta(days=1)

    aggregator = CsvAggregator(
        logger,
        settings.data_dir,
        start_date,
        end_date,
        settings.symbols,
        candle_length=settings.candle_length,
        unit=settings.unit,
    )

    candles = aggregator.get_candles()

    strategy = StaticBounce(
        logger,
        candles,
        0.03,  # proximity_threshold
        0.20,  # reward_points
        0.10,  # risk_points
        settings.price_tolerance,
        settings.min_separation,
        settings.top_n,
        15.0,  # decay_half_life_days
    )

    strategy.print_static_levels()

    total_pnl: float = 0.00
    position: Dict[str, Any] | None = None

    state: Dict[str, Any] = {
        "total_pnl": total_pnl,
        "position": position,
        "strategy": strategy,
    }

    filename = f"{settings.data_dir}/glbx-mdp3-{settings.backtest_date}.trades.csv"
    ticker = CsvTicker(filename, settings.symbols)

    await run_engine_async(ticker, logger, state, static_bounce_handler)

    log_with_color(
        logger,
        f"Total PnL on Day = ${state["total_pnl"]:.2f}{Style.RESET_ALL}",
        Fore.GREEN if state["total_pnl"] > 0 else Fore.RED,
        "info",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tunable support and resistance level finder"
    )
    BacktestSettings.set_args(parser)
    args = parser.parse_args()

    asyncio.run(main(args))
