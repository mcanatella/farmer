from __future__ import annotations

import asyncio
import csv
import time

from core import Tick
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Optional, Iterator, Iterable


# Helper that prunes down to the mircosecond and returns a datetime object
def _parse_ts_event(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1]
    if "." in ts:
        base, frac = ts.split(".", 1)
        ts = f"{base}.{(frac + '000000')[:6]}"
    return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)


class CsvTicker:
    """
    Streams trade ticks from a CME-style CSV (GLBX MDP3 trades dump).
    You can throttle playback via 'sleep' or run full speed.
    """

    def __init__(
        self,
        csv_path: str | Path,
        want_symbols: list[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        throttle: float = 0.0,
    ):
        self.csv_path = Path(csv_path)
        self.want_symbols = want_symbols
        self.start_time = start_time
        self.end_time = end_time
        self.throttle = throttle

    def _rows(self) -> Iterable[Tick]:
        with self.csv_path.open("r", newline="") as f:
            r = csv.reader(f)
            header = next(r)
            idx = {name: i for i, name in enumerate(header)}
            ts_event_i = idx["ts_event"]
            action_i = idx["action"]
            side_i = idx["side"]
            price_i = idx["price"]
            size_i = idx["size"]
            symbol_i = idx["symbol"]

            for row in r:
                try:
                    # We are only interested in trade events
                    if row[action_i] != "T":
                        continue

                    # Ignore irrelevant symbols
                    if row[symbol_i] not in self.want_symbols:
                        continue

                    t = _parse_ts_event(row[ts_event_i])
                    if self.start_time and t < self.start_time:
                        continue
                    if self.end_time and t > self.end_time:
                        continue

                    yield Tick(
                        t=t,
                        price=float(row[price_i]),
                        size=int(float(row[size_i])),
                        side=row[side_i],
                        symbol=row[symbol_i],
                    )
                except Exception as e:
                    # TODO: Log error
                    continue

    async def __aiter__(self) -> AsyncIterator[Tick]:
        for tick in self._rows():
            if self.throttle:
                await asyncio.sleep(self.throttle)
            yield tick

    def __iter__(self) -> Iterator[Tick]:
        for tick in self._rows():
            if self.throttle:
                time.sleep(self.throttle)
            yield tick
