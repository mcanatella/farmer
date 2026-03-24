import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from aggregators import CsvAggregator
from core import Strategy, run_engine_async
from models import BacktestConfig, BacktestResult, StrategyConfig
from strategies import MeanReversionEma, StaticBounce, StaticBounceWithDelta
from tickers import CsvTicker

from .handlers import mean_reversion_ema_handler, static_bounce_handler


def _build_strategy(
    config: StrategyConfig, logger: logging.Logger, candles: List[Dict[str, Any]]
) -> Strategy:
    if config.strategy_params.kind == "static_bounce":
        return StaticBounce(logger, candles, config.strategy_params)
    elif config.strategy_params.kind == "static_bounce_with_delta":
        return StaticBounceWithDelta(logger, candles, config.strategy_params)
    elif config.strategy_params.kind == "mean_reversion_ema":
        return MeanReversionEma(logger, candles, config.strategy_params)
    else:
        raise ValueError(f"Unsupported strategy kind: {config.strategy_params.kind}")


async def run_backtest_async(
    config: BacktestConfig,
    logger: Optional[logging.Logger] = None,
) -> List[BacktestResult]:
    if config.strategy.strategy_params.kind == "static_bounce":
        return await run_static_bounce_async(config, logger)
    elif config.strategy.strategy_params.kind == "static_bounce_with_delta":
        # We use the same runner method for both StaticBounce and StaticBounceWithDelta since
        # the only difference is the strategy logic, not the backtest flow or data requirements.
        # Note that this may not always be the case for future strategies.
        # It's ok to implement a new runner method if needed.
        return await run_static_bounce_async(config, logger)
    elif config.strategy.strategy_params.kind == "mean_reversion_ema":
        # Same runner flow works for now for this strategy
        return await run_static_bounce_async(config, logger)
    else:
        raise ValueError(
            f"Unsupported strategy kind: {config.strategy.strategy_params.kind}"
        )


async def run_static_bounce_async(
    config: BacktestConfig,
    logger: Optional[logging.Logger] = None,
) -> List[BacktestResult]:
    results: List[BacktestResult] = []
    if logger is None:
        logger = logging.getLogger("static_bounce_backtest_runner")

    for bt_date in config.dates:
        d = datetime.strptime(bt_date, "%Y%m%d").date()

        logger.info(f"Running backtest {config.name} for date: {d}")

        start_date = d - timedelta(
            days=config.strategy.aggregation_params.lookback_days
        )
        end_date = d - timedelta(days=1)

        # Currently only CsvAggregator is supported for backtesting
        if config.strategy.aggregation_params.data_source.kind != "csv":
            raise ValueError(
                f"Unsupported data_source for backtesting: {config.strategy.aggregation_params.data_source.kind}"
            )

        # Build a list of historical candles over the specified time window via CsvAggregator
        aggregator = CsvAggregator(
            logger, config.strategy.aggregation_params, start_date, end_date
        )
        candles = aggregator.get_candles()

        # Initialize / reset requested strategy
        strategy = _build_strategy(config.strategy, logger, candles)

        # Initialize / reset handler state
        state: Dict[str, Any] = {
            "total_pnl": 0.00,
            "position": None,
            "strategy": strategy,
            "tick_size": config.strategy.strategy_params.tick_size,
            "tick_value": config.strategy.strategy_params.tick_value,
        }

        trades_file = f"{config.strategy.aggregation_params.data_source.data_dir}/glbx-mdp3-{d:%Y%m%d}.trades.csv"

        if aggregator.current_symbol is None:
            raise ValueError("No symbol loaded in aggregator for backtest ticker")

        ticker = CsvTicker(trades_file, [aggregator.current_symbol])

        handler = (
            mean_reversion_ema_handler
            if config.strategy.strategy_params.kind == "mean_reversion_ema"
            else static_bounce_handler
        )

        await run_engine_async(ticker, logger, state, handler)

        results.append(
            BacktestResult(
                total_pnl=state["total_pnl"],
                trades_file=trades_file,
            )
        )

    return results
