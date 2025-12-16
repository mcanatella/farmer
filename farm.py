# mypy: ignore-errors

from calculators import CsvCalculator, ProjectXCalculator
from chart import Chart, Level
from config import BotSettings, DiscoverSettings, init_strucutred_logger
from projectx_client import Auth, MarketData, Orders

import argparse


def main(args):
    # Initialize the root logger
    logger = init_strucutred_logger()

    # Load settings from yaml config
    settings = BotSettings.load_yaml(args.config)

    auth = Auth(
        base_url=settings.api_base, username=settings.user, api_key=settings.api_key
    )

    jwt_token = auth.login()

    market_data_client = MarketData(settings.api_base, jwt_token)
    orders_client = Orders(settings.api_base, jwt_token)

    levels = []
    if args.auto:
        # Auto discover levels if flag is present
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

        support_dict, resistance_dict = calculator.calculate_and_print()

        for lvl in support_dict + resistance_dict:
            price = round(lvl["price"], 2)
            if args.exclude_level is None or price not in args.exclude_level:
                levels.append(
                    Level(
                        price,
                        name=None,
                        support=True,
                        resistance=True,
                        proximity_threshold=0.03,
                        reward_points=0.10,
                        risk_points=0.15,
                    )
                )
    else:
        # Otherwise use manually configured levels
        for level in settings.levels:
            value = level.pop("value")
            if args.exclude_level is None or value not in args.exclude_level:
                levels.append(Level(value, **level))

    chart = Chart(
        logger,
        settings.market_hub_base,
        jwt_token,
        market_data_client,
        orders_client,
        settings.account_id,
        settings.contract_id,
        settings.contract_size,
        levels=levels,
    )

    logger.info(
        "level farmer start", extra={"levels": [level.__dict__ for level in levels]}
    )

    # Start concurrent threads and block
    # chart.start_candle_poller()
    chart.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simple, tunable, algorithmic trading bot"
    )
    BotSettings.set_args(parser)
    DiscoverSettings.set_args(parser)
    args = parser.parse_args()

    main(args)
