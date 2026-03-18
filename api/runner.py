import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from aggregators import CsvAggregator
from calculations import DeltaWindow
from core import Strategy, run_engine_async
from models import BacktestConfig, BacktestResult, StrategyConfig
from strategies import StaticBounce, StaticBounceWithDelta
from tickers import CsvTicker

from .handlers import static_bounce_handler


def _build_strategy(
    config: StrategyConfig, logger: logging.Logger, candles: List[Dict[str, Any]]
) -> Strategy:
    if config.strategy_params.kind == "static_bounce":
        return StaticBounce(
            logger,
            candles,
            config.strategy_params.tick_size,
            config.strategy_params.proximity_threshold,
            config.strategy_params.reward_ticks,
            config.strategy_params.risk_ticks,
            config.strategy_params.tick_tolerance,
            config.strategy_params.min_separation,
            config.strategy_params.top_n,
            config.strategy_params.decay_half_life_days,
            config.strategy_params.precision,
        )
    elif config.strategy_params.kind == "static_bounce_with_delta":
        delta_window = DeltaWindow(
            window_seconds=config.strategy_params.delta_window_seconds
        )
        return StaticBounceWithDelta(
            logger,
            candles,
            config.strategy_params.tick_size,
            config.strategy_params.proximity_threshold,
            config.strategy_params.reward_ticks,
            config.strategy_params.risk_ticks,
            config.strategy_params.tick_tolerance,
            config.strategy_params.min_separation,
            config.strategy_params.top_n,
            config.strategy_params.decay_half_life_days,
            config.strategy_params.precision,
            delta_window,
            attempt_seconds=config.strategy_params.attempt_seconds,
            delta_ratio_threshold=config.strategy_params.delta_ratio_threshold,
            min_response_ticks=config.strategy_params.min_response_ticks,
            max_penetration_ticks=config.strategy_params.max_penetration_ticks,
            cooldown_seconds=config.strategy_params.cooldown_seconds,
        )
    else:
        raise ValueError(f"Unsupported strategy kind: {config.strategy_params.kind}")


async def run_backtest_async(
    config: BacktestConfig,
    logger: Optional[logging.Logger] = None,
) -> List[BacktestResult]:
    if config.strategy.strategy_params.kind == "static_bounce":
        return await run_static_bounce_async(config, logger)
    elif config.strategy.strategy_params.kind == "static_bounce_with_delta":
        return await run_static_bounce_with_delta_async(config, logger)
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
            logger,
            config.strategy.aggregation_params.data_source.data_dir,
            start_date,
            end_date,
            config.strategy.aggregation_params.data_source.symbols,
            config.strategy.aggregation_params.data_source.pct_margin,
            config.strategy.aggregation_params.data_source.abs_margin,
            config.strategy.aggregation_params.data_source.min_total_volume,
            candle_length=config.strategy.aggregation_params.candle_length,
            unit=config.strategy.aggregation_params.unit,
        )
        candles = aggregator.get_candles()

        # Initialize / reset requested strategy
        strategy = _build_strategy(config.strategy, logger, candles)

        # Initialize / reset handler state
        state: Dict[str, Any] = {
            "total_pnl": 0.0,
            "position": None,
            "strategy": strategy,
        }

        trades_file = f"{config.strategy.aggregation_params.data_source.data_dir}/glbx-mdp3-{d:%Y%m%d}.trades.csv"

        if aggregator.current_symbol is None:
            raise ValueError("No symbol loaded in aggregator for backtest ticker")

        ticker = CsvTicker(trades_file, [aggregator.current_symbol])

        await run_engine_async(ticker, logger, state, static_bounce_handler)

        results.append(
            BacktestResult(
                total_pnl=state["total_pnl"],
                trades_file=trades_file,
            )
        )

    return results


async def run_static_bounce_with_delta_async(
    config: BacktestConfig,
    logger: Optional[logging.Logger] = None,
) -> List[BacktestResult]:
    if logger is None:
        logger = logging.getLogger("static_bounce_with_delta_backtest_runner")

    return (
        []
    )  # Placeholder for future implementation of StaticBounceWithDelta backtesting
