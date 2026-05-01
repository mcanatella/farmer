import logging
from datetime import datetime, timedelta

from api.models import StrategyConfig
from core import Aggregator

from .csv import CsvAggregator
from .projectx import ProjectXAggregator


def build_aggregator(
    strategy_conf: StrategyConfig, logger: logging.Logger
) -> Aggregator:
    if strategy_conf.aggregation_params is None:
        raise ValueError("Aggregation parameters are required for this strategy")

    aggregator: Aggregator
    if strategy_conf.aggregation_params.data_source.kind == "projectx":
        aggregator = ProjectXAggregator(logger, strategy_conf.aggregation_params)
    elif strategy_conf.aggregation_params.data_source.kind == "csv":
        if strategy_conf.ticker_params is None:
            raise ValueError("Ticker parameters are required for CSV aggregation")

        today = datetime.now().date()
        start_date = today - timedelta(
            days=strategy_conf.aggregation_params.lookback_days
        )
        aggregator = CsvAggregator(
            logger,
            strategy_conf.aggregation_params,
            strategy_conf.ticker_params,
            start_date,
            today,
        )
    else:
        raise ValueError(
            f"Unsupported data_source: {strategy_conf.aggregation_params.data_source.kind}"
        )

    return aggregator
