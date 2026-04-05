import logging

from api.models import StrategyConfig
from .csv import CsvAggregator
from .projectx import ProjectXAggregator
from core import Aggregator
from datetime import datetime, timedelta


def build_aggregator(
    strategy_conf: StrategyConfig, logger: logging.Logger
) -> Aggregator:
    aggregator: Aggregator
    if strategy_conf.aggregation_params.data_source.kind == "projectx":
        aggregator = ProjectXAggregator(logger, strategy_conf.aggregation_params)
    elif strategy_conf.aggregation_params.data_source.kind == "csv":
        today = datetime.now().date()
        start_date = today - timedelta(
            days=strategy_conf.aggregation_params.lookback_days
        )
        aggregator = CsvAggregator(
            logger, strategy_conf.aggregation_params, start_date, today
        )
    else:
        raise ValueError(
            f"Unsupported data_source: {strategy_conf.aggregation_params.data_source.kind}"
        )

    return aggregator
