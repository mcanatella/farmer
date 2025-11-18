from pydantic import BaseModel
from typing import List, Dict, Any

import yaml


class Settings(BaseModel):
    api_base: str
    market_hub_base: str
    user: str
    api_key: str
    account_id: int
    contract_id: str
    contract_size: int
    levels: List[Dict[str, Any]]

    @classmethod
    def load_yaml(cls, path: str = "config.yaml") -> "Settings":
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        return cls(**data)

    @classmethod
    def set_args(cls, parser):
        parser.add_argument(
            "--config", type=str, default="config.yaml", help="Config file path"
        )
