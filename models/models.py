from typing import List, Literal, Union

from pydantic import BaseModel


class StaticBounceParams(BaseModel):
    tick_size: float
    proximity_threshold: int
    reward_ticks: int
    risk_ticks: int
    tick_tolerance: int
    kind: Literal["static_bounce"] = "static_bounce"
    min_separation: int = 10
    top_n: int = 10
    decay_half_life_days: float = 15.0


class VwapFadeParams(BaseModel):
    kind: Literal["vwap_fade"] = "vwap_fade"
    entry_band: float = 0.5
    stop_band: float = 1.0


StrategyParams = Union[StaticBounceParams, VwapFadeParams]


class CsvDataSource(BaseModel):
    kind: Literal["csv"] = "csv"
    data_dir: str
    symbols: List[str]


class ProjectXDataSource(BaseModel):
    kind: Literal["projectx"] = "projectx"
    base_url: str
    username: str
    api_key: str
    contract_id: str


DataSource = Union[CsvDataSource, ProjectXDataSource]


class AggregationParams(BaseModel):
    lookback_days: int
    data_source: DataSource
    candle_length: int = 5
    unit: str = "minutes"


class StrategyConfig(BaseModel):
    name: str
    aggregation_params: AggregationParams
    strategy_params: StrategyParams


class BacktestConfig(BaseModel):
    name: str
    dates: List[str]
    strategy: StrategyConfig


class BacktestResult(BaseModel):
    total_pnl: float
    trades_file: str
