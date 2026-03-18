from collections import deque
from dataclasses import dataclass
from datetime import datetime

from core import Tick


@dataclass
class DeltaEvent:
    t: datetime
    delta: int
    price: float
    size: int


class DeltaWindow:
    def __init__(self, window_seconds: float) -> None:
        self.window_seconds = window_seconds
        self.events: deque[DeltaEvent] = deque()
        self.sum_delta: int = 0
        self.sum_volume: int = 0

    def on_tick(self, tick: Tick) -> None:
        self.events.append(
            DeltaEvent(t=tick.t, delta=tick.delta(), price=tick.price, size=tick.size)
        )
        self.sum_delta += tick.delta()
        self.sum_volume += tick.size

        cutoff = tick.t.timestamp() - self.window_seconds
        while self.events and self.events[0].t.timestamp() < cutoff:
            old = self.events.popleft()
            self.sum_delta -= old.delta
            self.sum_volume -= old.size
