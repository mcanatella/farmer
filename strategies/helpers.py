import logging
from typing import Any, Dict, List

from api.models import StrategyConfig
from core import Strategy

from .mean_reversion_ema import MeanReversionEma
from .static_bounce import StaticBounce
from .static_bounce_with_delta import StaticBounceWithDelta


def build_strategy(
    config: StrategyConfig, logger: logging.Logger, candles: List[Dict[str, Any]]
) -> Strategy:
    if config.strategy_params.kind == "static_bounce":
        return StaticBounce(logger, candles, config.strategy_params)
    elif config.strategy_params.kind == "static_bounce_with_delta":
        return StaticBounceWithDelta(logger, candles, config.strategy_params)
    elif config.strategy_params.kind == "mean_reversion_ema":
        return MeanReversionEma(logger, candles, config.strategy_params)
    else:
        raise ValueError(f"Unsupported strategy kind: {config.strategy_params.kind}")
