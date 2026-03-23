import argparse
from datetime import date, datetime, timedelta

from aggregators import CsvAggregator, ProjectXAggregator
from config import DiscoverSettings, init_backtest_logger
from core import Aggregator
from projectx_client import Auth, MarketData
from strategies import StaticBounce


def main(args) -> None:
    logger = init_backtest_logger()

    settings = DiscoverSettings.build(args)

    # Look up the specified strategy in settings and raise an error if not present
    strategy_conf = None
    for s in settings.strategies:
        if s.name == args.strategy:
            strategy_conf = s
            break
    if strategy_conf is None:
        raise ValueError(f"Strategy '{args.strategy}' not found in configuration")

    aggregator: Aggregator
    if strategy_conf.aggregation_params.data_source.kind == "projectx":
        auth = Auth(
            base_url=strategy_conf.aggregation_params.data_source.base_url,
            username=strategy_conf.aggregation_params.data_source.username,
            api_key=strategy_conf.aggregation_params.data_source.api_key,
        )
        jwt_token = auth.login()
        market_data_client = MarketData(
            strategy_conf.aggregation_params.data_source.base_url, jwt_token
        )
        aggregator = ProjectXAggregator(
            logger, strategy_conf.aggregation_params, market_data_client
        )
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

    strategy = None
    if strategy_conf.strategy_params.kind == "static_bounce":
        strategy = StaticBounce(
            logger, aggregator.get_candles(), strategy_conf.strategy_params
        )
    else:
        raise ValueError(
            f"Unsupported strategy kind: {strategy_conf.strategy_params.kind}"
        )

    print(strategy)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tunable support and resistance level finder"
    )
    DiscoverSettings.set_args(parser)
    args = parser.parse_args()

    main(args)
