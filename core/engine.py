from dataclasses import dataclass
from .protocols import AsyncTicker, Ticker
from .types import Tick
from typing import Any, Awaitable, Callable, Dict

import asyncio


async def run_engine_async(
    ticker: AsyncTicker, on_tick: Callable[[Tick], Awaitable[None] | None]
):
    async for tick in ticker:
        res = on_tick(tick)
        if asyncio.iscoroutine(res):
            await res


def run_engine(ticker: Ticker, ontick: Callable[[Tick, Any], None]):
    for tick in ticker:
        ontick(tick)
