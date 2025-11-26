from pydantic import BaseModel

import yaml


class ApiSettings(BaseModel):
    base: str
    market_hub_base: str
    user: str
    key: str


class Settings(BaseModel):
    api: ApiSettings

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
