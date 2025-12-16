from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Optional, List

import yaml


class DiscoverApiSettings(BaseModel):
    base: str
    user: str
    key: str
    contract_id: str


class DiscoverSettings(BaseModel):
    data_source: str = (
        "projectx"  # Should specify either a supported api like "projectx" or "csv" for CsvAggregator
    )
    data_directory: Optional[str] = None  # Used only if data_source is "csv"
    symbols: Optional[List[str]] = None  # Used only if data_source is "csv"

    api: DiscoverApiSettings

    days: int = 10
    candle_length: int = 5
    unit: str = "minutes"
    top_n: int = 5
    min_separation: int = 10

    # It doesn't make sense to have defaults for price_tolerance, as it must be tuned depending on the asset being analyzed
    price_tolerance: float

    @classmethod
    def build(cls, args) -> "DiscoverSettings":
        with open(args.config, "r") as f:
            raw = yaml.safe_load(f) or {}

        data = raw.get("discover", {})

        overrides: Dict = {}

        if args.data_source is not None:
            overrides["data_source"] = args.data_source

        if args.data_directory is not None:
            overrides["data_directory"] = args.data_directory

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

        api_overrides: Dict = {}

        if args.api_base is not None:
            api_overrides["base"] = args.api_base

        if args.api_user is not None:
            api_overrides["user"] = args.api_user

        if args.api_key is not None:
            api_overrides["key"] = args.api_key

        if args.api_contract_id is not None:
            api_overrides["contract_id"] = args.api_contract_id

        if api_overrides:
            data.setdefault("api", {}).update(api_overrides)

        return cls(**data)

    def custom_validate(self) -> None:
        # Add custom validation logic here
        if self.data_source == "csv":
            if not self.data_directory:
                raise ValueError(
                    "data_directory must be specified when data_source is 'csv'"
                )
            if not self.symbols:
                raise ValueError("symbols must be specified when data_source is 'csv'")

        if self.data_source != "csv":
            if self.data_directory:
                raise ValueError(
                    "data_directory should only be specified when data_source is 'csv'"
                )
            if self.symbols:
                raise ValueError(
                    "symbols should only be specified when data_source is 'csv'"
                )

    @classmethod
    def set_args(cls, parser):
        # Config file settings
        parser.add_argument(
            "--config", type=str, default="config.yaml", help="Config file path"
        )

        # Data source settings
        parser.add_argument(
            "--data-source",
            type=str,
            help="The data source to use; either 'projectx' or 'csv'",
        )
        parser.add_argument(
            "--data-directory",
            type=str,
            help="The directory containing CSV files; used only if data source is 'csv'",
        )
        parser.add_argument(
            "--symbols",
            nargs="+",
            type=str,
            help="List of symbols to analyze; used only if data source is 'csv'",
        )

        # Api settings
        parser.add_argument(
            "--api-base",
            type=str,
            help="The discovery api base url",
        )
        parser.add_argument(
            "--api-user",
            type=str,
            help="The discovery api username",
        )
        parser.add_argument(
            "--api-key",
            type=str,
            help="The discovery api key",
        )
        parser.add_argument(
            "--api-contract-id",
            type=str,
            help="The the contract id to analyze",
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
