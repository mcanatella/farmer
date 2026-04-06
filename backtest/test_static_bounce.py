import asyncio
import math
from pathlib import Path
from typing import List

import pytest

from api.models import (
    AggregationParams,
    BacktestConfig,
    BacktestResponse,
    CsvDataSource,
    StaticBounceParams,
    StrategyConfig,
)
from config import init_null_logger

from . import run_static_bounce_async


def run_static_bounce_backtest(
    data_dir: Path,
    dates: List[str],
    symbols: List[str],
    tick_size: float = 0.01,
    tick_value: float = 1.0,
    proximity_threshold: int = 3,
    reward_ticks: int = 20,
    risk_ticks: int = 10,
    tick_tolerance: int = 5,
    min_separation: int = 10,
    top_n: int = 5,
    decay_half_life_days: float = 15.0,
    lookback_days: int = 10,
    precision: int = 2,
) -> BacktestResponse:
    """
    Sync wrapper so unit tests can stay non-async.
    """
    logger = init_null_logger()

    config = BacktestConfig(
        name="static_bounce_backtest",
        dates=dates,
        strategy=StrategyConfig(
            name="static_bounce_strategy",
            aggregation_params=AggregationParams(
                lookback_days=lookback_days,
                data_source=CsvDataSource(
                    data_dir=str(data_dir),
                    symbols=symbols,
                    pct_margin=0.10,
                    abs_margin=200,
                    min_total_volume=1000,
                ),
                candle_length=5,
                unit="minutes",
            ),
            strategy_params=StaticBounceParams(
                tick_size=tick_size,
                tick_value=tick_value,
                proximity_threshold=proximity_threshold,
                reward_ticks=reward_ticks,
                risk_ticks=risk_ticks,
                tick_tolerance=tick_tolerance,
                min_separation=min_separation,
                top_n=top_n,
                decay_half_life_days=decay_half_life_days,
                precision=precision,
            ),
        ),
    )

    return asyncio.run(run_static_bounce_async(config, logger))


@pytest.mark.parametrize(
    "dates,symbols,tick_size,tick_value,proximity_threshold,reward_ticks,risk_ticks,tick_tolerance,"
    "min_separation,top_n,decay_half_life_days,lookback_days,precision",
    [
        pytest.param(
            [
                "20251212",
                "20251214",
            ],
            ["CLZ5", "CLF6"],
            0.01,
            10.00,
            3,
            20,
            10,
            5,
            10,
            10,
            15.0,
            10,
            2,
            id="baseline",
        ),
    ],
)
def test_static_bounce(
    dates: List[str],
    symbols: List[str],
    tick_size: float,
    tick_value: float,
    proximity_threshold: int,
    reward_ticks: int,
    risk_ticks: int,
    tick_tolerance: int,
    min_separation: int,
    top_n: int,
    decay_half_life_days: float,
    lookback_days: int,
    precision: int,
) -> None:
    test_dir = Path(__file__).resolve().parent
    data_dir = test_dir / "testdata"

    response = run_static_bounce_backtest(
        data_dir=data_dir,
        dates=dates,
        symbols=symbols,
        tick_size=tick_size,
        tick_value=tick_value,
        proximity_threshold=proximity_threshold,
        reward_ticks=reward_ticks,
        risk_ticks=risk_ticks,
        tick_tolerance=tick_tolerance,
        min_separation=min_separation,
        top_n=top_n,
        decay_half_life_days=decay_half_life_days,
        lookback_days=lookback_days,
        precision=precision,
    )

    # Basic sanity assertions
    assert len(response.results) == len(dates)
    assert isinstance(response, BacktestResponse)
    assert isinstance(response.total_pnl, float)
    assert math.isfinite(response.total_pnl)
