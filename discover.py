from calculators import CsvCalculator, ProjectXCalculator  # TODO: support CsvCalculator
from config import DiscoverSettings
from projectx_client import Auth, MarketData

import argparse


def main(args):
    settings = DiscoverSettings.build(args)

    auth = Auth(
        base_url=settings.api.base, username=settings.api.user, api_key=settings.api.key
    )

    jwt_token = auth.login()
    market_data_client = MarketData(settings.api.base, jwt_token)

    # TODO: support multiple calculator types
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

    calculator.calculate_and_print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tunable support and resistance level finder"
    )
    DiscoverSettings.set_args(parser)
    args = parser.parse_args()

    main(args)
