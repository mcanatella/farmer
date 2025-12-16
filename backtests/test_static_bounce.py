from aggregators import CsvAggregator
from colorama import Fore
from config import log_with_color
from core import Tick, run_engine_async
from pathlib import Path
from datetime import date, timedelta
from strategies import StaticBounce
from tabulate import tabulate
from tickers import CsvTicker
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import asyncio
import logging
import math
import pytest

from config import init_backtest_logger


def init_null_logger() -> logging.Logger:
    """
    Logger that won't spam stdout during tests.
    """
    logger = logging.getLogger("static_bounce_test")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    return logger


def static_bounce_handler(
    tick: Tick, logger: logging.Logger, state: Dict[str, Any]
) -> None:
    if state["position"] is None:
        state["position"] = state["strategy"].check(tick.price, tick.t)
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


async def run_static_bounce_backtest_async(
    data_dir: Path,
    backtest_date: date,
    symbols: List[str],
    *,
    proximity_threshold: float,
    reward_points: float,
    risk_points: float,
    price_tolerance: float,
    min_separation: int,
    top_n: int,
    decay_half_life_days: float,
    lookback_days: int,
) -> float:
    """
    Run a static bounce backtest for the given date and return the total PnL.
    """
    logger = init_backtest_logger()

    start_date = backtest_date - timedelta(days=lookback_days)
    end_date = backtest_date - timedelta(days=1)

    # Build a list of historical candles over the specified time window via CsvAggregator
    aggregator = CsvAggregator(
        logger,
        data_dir,
        start_date,
        end_date,
        symbols,
        candle_length=5,  # TODO: Support more than 5 min candles
        unit="minutes",
    )
    candles = aggregator.get_candles()

    # Initialize StaticBounce strategy
    strategy = StaticBounce(
        logger,
        candles,
        proximity_threshold,
        reward_points,
        risk_points,
        price_tolerance,
        min_separation,
        top_n,
        decay_half_life_days,
    )

    strategy.print_static_levels()

    # Initialize handler state
    state: Dict[str, Any] = {
        "total_pnl": 0.0,
        "position": None,
        "strategy": strategy,
    }

    trades_file = data_dir / f"glbx-mdp3-{backtest_date:%Y%m%d}.trades.csv"
    ticker = CsvTicker(str(trades_file), symbols)

    # Run engine with static bounce handler
    await run_engine_async(ticker, logger, state, static_bounce_handler)

    return state["total_pnl"]


def run_static_bounce_backtest(
    data_dir: Path,
    backtest_date: date,
    symbols: List[str],
    **kwargs: Any,
) -> float:
    """
    Sync wrapper so tests can stay non-async.
    """
    return asyncio.run(
        run_static_bounce_backtest_async(
            data_dir=data_dir,
            backtest_date=backtest_date,
            symbols=symbols,
            **kwargs,
        )
    )


@pytest.mark.parametrize(
    "proximity_threshold,reward_points,risk_points,price_tolerance,"
    "min_separation,top_n,decay_half_life_days,lookback_days",
    [
        pytest.param(
            0.03,  # proximity_threshold
            0.20,  # reward_points
            0.10,  # risk_points
            0.05,  # price_tolerance
            10,  # min_separation
            10,  # top_n
            15.0,  # decay_half_life_days
            10,  # lookback_days
            id="baseline",
        ),
    ],
)
def test_static_bounce_baseline_params(
    proximity_threshold: float,
    reward_points: float,
    risk_points: float,
    price_tolerance: float,
    min_separation: int,
    top_n: int,
    decay_half_life_days: float,
    lookback_days: int,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "cl_historical"
    backtest_date = date(2025, 12, 10)
    symbols = ["CLZ5", "CLF6"]

    total_pnl = run_static_bounce_backtest(
        data_dir=data_dir,
        backtest_date=backtest_date,
        symbols=symbols,
        proximity_threshold=proximity_threshold,
        reward_points=reward_points,
        risk_points=risk_points,
        price_tolerance=price_tolerance,
        min_separation=min_separation,
        top_n=top_n,
        decay_half_life_days=decay_half_life_days,
        lookback_days=lookback_days,
    )

    # Basic sanity assertions
    assert isinstance(total_pnl, float)
    assert math.isfinite(total_pnl)

    # Print a one-row table so you can compare PnL across params
    row = [
        proximity_threshold,
        reward_points,
        risk_points,
        price_tolerance,
        min_separation,
        top_n,
        round(total_pnl, 2),
    ]
    headers = [
        "prox_thresh",
        "reward",
        "risk",
        "price_tol",
        "min_sep",
        "top_n",
        "PnL",
    ]

    print()
    print(tabulate([row], headers=headers, tablefmt="pretty"))
