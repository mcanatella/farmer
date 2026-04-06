from datetime import datetime, timedelta
from typing import List, Literal, Optional, Union

from pydantic import BaseModel


class StaticBounceParams(BaseModel):
    tick_size: float
    tick_value: float
    proximity_threshold: int
    reward_ticks: int
    risk_ticks: int
    tick_tolerance: int
    kind: Literal["static_bounce"] = "static_bounce"
    min_separation: int = 10
    top_n: int = 10
    decay_half_life_days: float = 15.0
    precision: int = 2


class StaticBounceWithDeltaParams(BaseModel):
    tick_size: float
    tick_value: float
    proximity_threshold: int
    reward_ticks: int
    risk_ticks: int
    tick_tolerance: int
    kind: Literal["static_bounce_with_delta"] = "static_bounce_with_delta"
    min_separation: int = 10
    top_n: int = 10
    decay_half_life_days: float = 15.0
    precision: int = 2
    delta_window_seconds: float = 300.0
    attempt_seconds: int = 30
    delta_ratio_threshold: float = 0.20
    min_response_ticks: int = 3
    max_penetration_ticks: int = 4
    cooldown_seconds: int = 120


class MeanReversionEmaParams(BaseModel):
    tick_size: float
    tick_value: float
    entry_distance_ticks: int  # min ticks from EMA to trigger entry
    risk_ticks: int  # stop loss distance from entry in ticks
    kind: Literal["mean_reversion_ema"] = "mean_reversion_ema"
    precision: int = 2
    ema_period: int = 20  # EMA lookback in candles
    atr_period: int = 14  # ATR lookback in candles (14 is the standard)
    candle_length: int = 5  # minutes per candle (must match aggregation_params)
    reward_ticks: int = 0  # only used when target_ema is False
    target_ema: bool = True  # TP at the EMA level itself
    cooldown_seconds: int = 300  # seconds between trades
    max_distance_ticks: Optional[int] = (
        None  # skip entries if price is too far (knife-catcher guard)
    )
    max_atr: Optional[float] = None  # skip entries when ATR exceeds this value


StrategyParams = Union[
    StaticBounceParams, StaticBounceWithDeltaParams, MeanReversionEmaParams
]


class CsvDataSource(BaseModel):
    kind: Literal["csv"] = "csv"
    data_dir: str
    symbols: List[str]
    pct_margin: float
    abs_margin: int
    min_total_volume: int


class ProjectXDataSource(BaseModel):
    kind: Literal["projectx"] = "projectx"
    base_url: str
    market_hub_base_url: str
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
    dates: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    exclude_dates: Optional[List[str]] = None
    strategy: StrategyConfig

    def get_dates(self) -> List[str]:
        if self.dates:
            return self.dates

        if self.start_date and self.end_date:
            start = datetime.strptime(self.start_date, "%Y%m%d").date()
            end = datetime.strptime(self.end_date, "%Y%m%d").date()

            result = []
            d = start
            while d <= end:
                if d.weekday() != 5:  # Skip Saturdays
                    result.append(d.strftime("%Y%m%d"))
                d += timedelta(days=1)
        else:
            raise ValueError(
                "BacktestConfig requires either 'dates' or both 'start_date' and 'end_date'"
            )

        if self.exclude_dates:
            exclude_set = set(self.exclude_dates)
            result = [d for d in result if d not in exclude_set]

        return result


class BacktestResult(BaseModel):
    pnl: float
    trades_file: str


class BacktestResponse(BaseModel):
    backtest_name: str
    total_pnl: float
    results: List[BacktestResult]
