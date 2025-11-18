from calculators import CsvCalculator, ProjectXCalculator # TODO: support CsvCalculator
from config import Settings, DiscoverSettings
from projectx_client import Auth, MarketData

import argparse


def main(args):
    # Load settings from yaml config
    settings = Settings.load_yaml(args.config)

    auth = Auth(
        base_url=settings.api_base, username=settings.user, api_key=settings.api_key
    )

    jwt_token = auth.login()
    market_data_client = MarketData(settings.api_base, jwt_token)

    # TODO: support multiple calculator types
    calculator = ProjectXCalculator(
        market_data_client,
        settings.contract_id,
        days=args.days,
        candle_length=args.candle_length,
        unit="minutes",
        price_tolerance=args.price_tolerance,
        min_separation=args.min_separation,
        top_n=args.top_n,
    )

    calculator.calculate_and_print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tunable support and resistance level finder"
    )
    Settings.set_args(parser)
    DiscoverSettings.set_args(parser)
    args = parser.parse_args()

    main(args)
