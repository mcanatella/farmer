import argparse

from config import FarmSettings, init_strucutred_logger
from farm import Farmer


def main(args):
    logger = init_strucutred_logger()

    settings = FarmSettings.build(args)

    # Look up the specified strategy in settings and raise an error if not present
    strategy_conf = None
    for s in settings.strategies:
        if s.name == args.strategy:
            strategy_conf = s
            break
    if strategy_conf is None:
        raise ValueError(f"Strategy '{args.strategy}' not found in configuration")

    farmer = Farmer(strategy_conf, logger)

    farmer.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Modular quant trading bot",
    )
    FarmSettings.set_args(parser)
    args = parser.parse_args()

    main(args)
