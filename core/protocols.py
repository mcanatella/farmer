from .types import Tick
from typing import Any, AsyncIterator, Iterator, Protocol


# Pseudo interface for anything that can stream tick objects synchronously
class Ticker(Protocol):
    def __iter__(self) -> Iterator[Tick]: ...


# Pseudo interface for anything that can stream tick objects asynchronously
class AsyncTicker(Protocol):
    def __aiter__(self) -> AsyncIterator[Tick]: ...


# Pseudo interface for anything that can calculate support and resistance levels
# TODO: Calculate should return a list of Level objects
class Calculator(Protocol):
    def calculate(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...
