from pydantic import BaseModel
from typing import Dict, List

import yaml


class BacktestSettings(BaseModel):
    backtest_date: str
    data_dir: str
    symbols: List[str]

    days: int = 10
    candle_length: int = 5
    unit: str = "minutes"
    top_n: int = 5
    min_separation: int = 10

    # It doesn't make sense to have defaults for price_tolerance, as it must be tuned depending on the asset being analyzed
    price_tolerance: float

    @classmethod
    def build(cls, args) -> "BacktestSettings":
        with open(args.config, "r") as f:
            raw = yaml.safe_load(f) or {}

        data = raw.get("backtest", {})

        overrides: Dict = {}

        if args.backtest_date is not None:
            overrides["backtest_date"] = args.backtest_date

        if args.data_dir is not None:
            overrides["data_dir"] = args.data_dir

        if args.symbols is not None:
            overrides["symbols"] = args.symbols

        if args.days is not None:
            overrides["days"] = args.days

        if args.candle_length is not None:
            overrides["candle_length"] = args.candle_length

        if args.unit is not None:
            overrides["unit"] = args.unit

        if args.price_tolerance is not None:
            overrides["price_tolerance"] = args.price_tolerance

        if args.min_separation is not None:
            overrides["min_separation"] = args.min_separation

        if args.top_n is not None:
            overrides["top_n"] = args.top_n

        if overrides:
            data.update(overrides)

        return cls(**data)

    def custom_validate(self) -> None:
        pass

    @classmethod
    def set_args(cls, parser):
        # Config file settings
        parser.add_argument(
            "--config", type=str, default="config.yaml", help="Config file path"
        )

        # Backtest settings
        parser.add_argument(
            "--backtest-date",
            type=str,
            help="The date to backtest",
        )
        parser.add_argument(
            "--data-dir",
            type=str,
            help="Specifies the data directory containing tick data files",
        )
        parser.add_argument(
            "--symbols",
            nargs="+",
            type=str,
            help="List of symbols to analyze",
        )

        # Calculator settings
        parser.add_argument(
            "--days",
            type=int,
            help="The number of days back (from now) to analyze",
        )
        parser.add_argument("--candle-length", type=int, help="The candle timeframe")
        parser.add_argument(
            "--unit",
            type=str,
            help="The unit used to measure the candle length; only minutes or hours supported",
        )
        parser.add_argument(
            "--price-tolerance",
            type=float,
            help="Price range within which levels are considered the same",
        )
        parser.add_argument(
            "--min-separation",
            type=int,
            help="Number of candles before/after to consider a high/low isolated",
        )
        parser.add_argument(
            "--top-n",
            type=int,
            help="Number of support/resistance levels to return",
        )
