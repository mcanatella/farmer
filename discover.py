from calculators import CsvCalculator, ProjectXCalculator  # TODO: support CsvCalculator
from config import DiscoverSettings, init_backtest_logger
from core import Calculator
from datetime import datetime, timedelta
from projectx_client import Auth, MarketData

import argparse


def main(args) -> None:
    settings = DiscoverSettings.build(args)
    settings.validate()

    auth = Auth(
        base_url=settings.api.base, username=settings.api.user, api_key=settings.api.key
    )

    jwt_token = auth.login()
    market_data_client = MarketData(settings.api.base, jwt_token)

    calculator: Calculator
    if settings.data_source == "projectx":
        calculator = ProjectXCalculator(
            market_data_client,
            settings.api.contract_id,
            days=settings.days,
            candle_length=settings.candle_length,
            unit=settings.unit,
            price_tolerance=settings.price_tolerance,
            min_separation=settings.min_separation,
            top_n=settings.top_n,
        )
    elif settings.data_source == "csv":
        logger = init_backtest_logger()
        today = datetime.now().date()
        start_date = today - timedelta(days=args.days)
        calculator = CsvCalculator(
            logger,
            settings.data_directory,
            start_date,
            today,
            settings.symbols,
            candle_length=settings.candle_length,
            unit=settings.unit,
            price_tolerance=settings.price_tolerance,
            min_separation=settings.min_separation,
            top_n=settings.top_n,
        )
    else:
        raise ValueError(f"Unsupported data_source: {settings.data_source}")

    calculator.calculate_and_print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tunable support and resistance level finder"
    )
    DiscoverSettings.set_args(parser)
    args = parser.parse_args()

    main(args)
