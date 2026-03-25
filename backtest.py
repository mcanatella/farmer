import argparse
import asyncio
import json

from api import run_backtest_async
from config import BacktestSettings, init_backtest_logger


async def main(args) -> None:
    settings = BacktestSettings.build(args)

    logger = init_backtest_logger()

    backtest_conf = None
    for bt in settings.backtests:
        if bt.name == args.name:
            backtest_conf = bt
            break
    if backtest_conf is None:
        raise ValueError(f"Backtest '{args.name}' not found in configuration")

    response = await run_backtest_async(backtest_conf, logger)

    print(json.dumps(response.model_dump(), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Quant trading backtest runner for modular strategies",
    )
    BacktestSettings.set_args(parser)
    args = parser.parse_args()

    asyncio.run(main(args))
