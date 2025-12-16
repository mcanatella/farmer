from aggregators import ProjectXAggregator, CsvAggregator
from config import DiscoverSettings, init_backtest_logger
from core import Aggregator
from datetime import datetime, timedelta
from projectx_client import Auth, MarketData
from strategies import StaticBounce

import argparse


def main(args) -> None:
    logger = init_backtest_logger()

    settings = DiscoverSettings.build(args)
    settings.custom_validate()

    aggregator: Aggregator
    if settings.data_source == "projectx":
        auth = Auth(
            base_url=settings.api.base,
            username=settings.api.user,
            api_key=settings.api.key,
        )
        jwt_token = auth.login()
        market_data_client = MarketData(settings.api.base, jwt_token)

        aggregator = ProjectXAggregator(
            logger,
            market_data_client,
            settings.api.contract_id,
            settings.days,
            settings.candle_length,
            unit=settings.unit,
        )
    elif settings.data_source == "csv":
        today = datetime.now().date()
        start_date = today - timedelta(days=args.days)

        if settings.data_directory is None:
            raise ValueError("--data_directory is required when --data-source=csv")

        if settings.symbols is None:
            raise ValueError("--symbols is required when --data-source=csv")

        aggregator = CsvAggregator(
            logger,
            settings.data_directory,
            start_date,
            today,
            settings.symbols,
            candle_length=settings.candle_length,
            unit=settings.unit,
        )
    else:
        raise ValueError(f"Unsupported data_source: {settings.data_source}")

    strategy = StaticBounce(
        logger,
        aggregator.get_candles(),
        0.00,  # proximity_threshold unused when simply discovering signal data
        0.00,  # reward_points unused when simply discovering signal data
        0.00,  # risk_points unused when simply discovering signal data
        settings.price_tolerance,
        settings.min_separation,
        settings.top_n,
        15.0,  # decay_half_life_days
    )

    strategy.print_static_levels()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tunable support and resistance level finder"
    )
    DiscoverSettings.set_args(parser)
    args = parser.parse_args()

    main(args)
