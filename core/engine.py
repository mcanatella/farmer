from dataclasses import dataclass
from .protocols import AsyncTicker, Ticker
from .types import Tick
from typing import Any, Awaitable, Callable, Dict

import asyncio


@dataclass
class EngineState:
    position: Dict[str, Any] = None
    market_price: int = 0
    profit_loss: int = 0


async def run_engine_async(
    ticker: AsyncTicker, state: Any, on_tick: Callable[[Tick], Awaitable[None] | None]
):
    async for tick in ticker:
        res = on_tick(tick, state)
        if asyncio.iscoroutine(res):
            await res


def run_engine(ticker: Ticker, state: Any, ontick: Callable[[Tick, Any], None]):
    for tick in ticker:
        ontick(tick, state)
