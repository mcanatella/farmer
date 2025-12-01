from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict

import yaml


class DiscoverApiSettings(BaseModel):
    base: str
    user: str
    key: str
    contract_id: str


class DiscoverSettings(BaseModel):
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

    @classmethod
    def set_args(cls, parser):
        # Config file settings
        parser.add_argument(
            "--config", type=str, default="config.yaml", help="Config file path"
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
