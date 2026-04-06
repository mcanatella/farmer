from typing import List

import yaml
from pydantic import BaseModel

from api.models import StrategyConfig


class DiscoverSettings(BaseModel):
    strategies: List[StrategyConfig]

    @classmethod
    def build(cls, args) -> "DiscoverSettings":
        with open(args.config, "r") as f:
            raw = yaml.safe_load(f) or {}

        data = raw.get("discover", {})

        return cls(**data)

    @classmethod
    def set_args(cls, parser):
        parser.add_argument(
            "--config", type=str, default="config.yaml", help="Config file path"
        )

        parser.add_argument(
            "--strategy", type=str, help="The strategy name to run discovery for"
        )
