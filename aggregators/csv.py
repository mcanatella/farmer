import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

from api.models import AggregationParams, TickerParams
from core import Tick, run_engine
from tickers import CsvTicker

FNAME_PREFIX = "glbx-mdp3-"
FNAME_POSTFIX = ".trades.csv"
FNAME_RE = re.compile(rf"{re.escape(FNAME_PREFIX)}(\d{{8}}){re.escape(FNAME_POSTFIX)}$")


# Helper that floors to the nearest 5-minute mark and returns a datetime object
def _floor_min(dt: datetime, minute_interval: int = 5) -> datetime:
    m = dt.minute - (dt.minute % minute_interval)
    return dt.replace(minute=m, second=0, microsecond=0)


# Helper that parses YYYYMMDD string into a date object
def _parse_yyyymmdd(s: str) -> date:
    """
    Parses a YYYYMMDD string into a date object.
    """
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _csv_aggregator_handler(
    tick: Tick, logger: logging.Logger, state: Dict[str, Any]
) -> None:
    """
    Aggregation handler that builds OHLCV candles in-memory as it streams ticks.
    The bucket timestamp is the floor of the tick time to the nearest candle length.
    """
    bkt = _floor_min(tick.t, state["candle_length"]), tick.symbol
    rec = state["buckets"].get(bkt)
    if rec is None:
        # open=first price, high/low init to price, close updates, volume sums
        state["buckets"][bkt] = {
            "o": tick.price,
            "h": tick.price,
            "l": tick.price,
            "c": tick.price,
            "v": tick.size,
        }
    else:
        if tick.price > rec["h"]:
            rec["h"] = tick.price
        if tick.price < rec["l"]:
            rec["l"] = tick.price
        rec["c"] = tick.price
        rec["v"] += tick.size


class CsvAggregator:
    """
    Aggregator that streams trade ticks from one or more CSV files via CsvTicker and builds OHLCV candles in-memory.
    The bucket timestamp is the floor of the tick time to the nearest candle length.
    """

    def __init__(
        self,
        logger: logging.Logger,
        params: AggregationParams,
        ticker_params: TickerParams,
        start_date: date,
        end_date: date,
    ) -> None:
        if ticker_params.data_source.kind != "csv":
            raise ValueError(
                f"Invalid data source for CsvAggregator: {ticker_params.data_source.kind}"
            )

        self.logger = logger
        self.params = params
        self.ticker_params = ticker_params
        self.start_date = start_date
        self.end_date = end_date

        self.data_dir = Path(ticker_params.data_source.data_dir)
        self.candles: List[Dict[str, Any]] = []

    def get_candles(self) -> List[Dict[str, Any]]:
        self._poll()

        return self.candles

    def _poll(self) -> None:
        # OHLCV state accumulator keyed by (bucket_ts, symbol)
        buckets: Dict[tuple[datetime, str], Dict[str, float]] = {}

        # Collect matching files by filename date
        dates: List[date] = []
        for path in sorted(self.data_dir.glob("glbx-mdp3-*.trades.csv")):
            m = FNAME_RE.search(path.name)
            if not m:
                continue
            d = _parse_yyyymmdd(m.group(1))
            if self.start_date <= d <= self.end_date:
                dates.append(d)

        state: Dict[str, Any] = {
            "buckets": buckets,
            "candle_length": self.params.candle_length,
        }

        for d in dates:
            ticker = CsvTicker(self.logger, self.ticker_params, d.strftime("%Y%m%d"))
            run_engine(ticker, self.logger, state, _csv_aggregator_handler)

            # Carry forward the leader contract to the next file
            self.ticker_params.start_symbol = ticker.current_symbol

        if not buckets:
            raise RuntimeError(
                f"No candles produced. current_symbol={ticker.current_symbol} "
                f"symbols={self.ticker_params.symbols} vols={ticker.symbol_volumes}"
            )

        # Flatten to list of dicts, sorted by time then symbol
        out: List[Dict[str, Any]] = []
        for (bkt_ts, sym), rec in sorted(
            buckets.items(), key=lambda x: (x[0][0], x[0][1])
        ):
            out.append(
                {
                    "t": bkt_ts.isoformat().replace("+00:00", "Z"),
                    "symbol": sym,
                    "o": round(rec["o"], 3),
                    "h": round(rec["h"], 3),
                    "l": round(rec["l"], 3),
                    "c": round(rec["c"], 3),
                    "v": int(rec["v"]),
                }
            )

        self.candles = out
