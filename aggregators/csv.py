import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core import Tick, run_engine
from tickers import CsvTicker

FNAME_PREFIX = "glbx-mdp3-"
FNAME_POSTFIX = ".trades.csv"
FNAME_RE = re.compile(rf"{re.escape(FNAME_PREFIX)}(\d{{8}}){re.escape(FNAME_POSTFIX)}$")


# Helper that floors to the nearest 5-minute mark and returns a datetime object
def _floor_5min(dt: datetime) -> datetime:
    m = dt.minute - (dt.minute % 5)
    return dt.replace(minute=m, second=0, microsecond=0)


# Helper that parses YYYYMMDD string into a date object
def _parse_yyyymmdd(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _csv_aggregator_handler(
    tick: Tick, logger: logging.Logger, state: Dict[str, Any]
) -> None:
    # Ignore ticks from symbols not in allowed list
    if tick.symbol not in state["allowed_symbols"]:
        return

    # Initialize current_symbol lazily
    if state["current_symbol"] is None:
        state["current_symbol"] = tick.symbol

    state["symbols_used"].add(tick.symbol)

    # Update symbol volumes
    state["symbol_volumes"][tick.symbol] += tick.size

    vols = state["symbol_volumes"]
    current = state["current_symbol"]

    # pct_margin = 0.10  # 10% margin to switch contracts
    # abs_margin = 200  # contracts lead required (in volume) to switch regardless of pct margin
    # min_total_volume = 1000  # minimum total volume to consider switching

    leader = max(vols, key=vols.get)
    if leader != current:
        total = sum(vols.values())
        lead = vols[leader] - vols[current]

        if total >= state["min_total_volume"] and (
            lead >= state["abs_margin"]
            or vols[leader] >= vols[current] * (1 + state["pct_margin"])
        ):
            logger.info(
                f"Switching from {current} to {leader} at {tick.t.isoformat()} with volumes: {vols}"
            )
            state["current_symbol"] = leader
            current = leader

    if tick.symbol != current:
        return

    bkt = _floor_5min(tick.t), tick.symbol
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
    def __init__(
        self,
        logger: logging.Logger,
        data_dir: str | Path,
        start_date: date,
        end_date: date,
        symbols: List[str],
        pct_margin: float,
        abs_margin: int,
        min_total_volume: int,
        candle_length: Optional[int] = 5,  # TODO: Actually use this
        unit: Optional[str] = "minutes",  # TODO: Actually use this
    ) -> None:
        self.logger = logger
        self.data_dir = Path(data_dir)
        self.start_date = start_date
        self.end_date = end_date

        self.symbols = symbols
        self.start_symbol = self.symbols[0]
        self.pct_margin = pct_margin
        self.abs_margin = abs_margin
        self.min_total_volume = min_total_volume

        self.unit = 3 if unit == "hours" else 2
        self.candle_length = candle_length

        # TODO: Define candle type instead of using a Dict
        self.candles: List[Dict[str, Any]] = []

        self.symbols_used: Set[str] = set()
        self.current_symbol: Optional[str] = None

    def get_candles(self) -> List[Dict[str, Any]]:
        self._poll()

        return self.candles

    def _poll(self) -> None:
        # OHLCV state accumulator keyed by (bucket_ts, symbol)
        buckets: Dict[tuple[datetime, str], Dict[str, float]] = {}

        symbol_volumes: Dict[str, int] = {self.start_symbol: 0}
        for sym in self.symbols:
            symbol_volumes[sym] = 0

        # current_symbol = self.start_symbol

        # Collect matching files by filename date
        files: List[Path] = []
        for p in sorted(self.data_dir.glob("glbx-mdp3-*.trades.csv")):
            m = FNAME_RE.search(p.name)
            if not m:
                continue
            d = _parse_yyyymmdd(m.group(1))
            if self.start_date <= d <= self.end_date:
                files.append(p)

        state: Dict[str, Any] = {
            "buckets": buckets,
            "symbol_volumes": symbol_volumes,
            "current_symbol": None,
            "allowed_symbols": self.symbols,
            "symbols_used": set(),
            "pct_margin": self.pct_margin,
            "abs_margin": self.abs_margin,
            "min_total_volume": self.min_total_volume,
        }

        for fp in files:
            ticker = CsvTicker(fp, self.symbols)

            run_engine(ticker, self.logger, state, _csv_aggregator_handler)

            # Reset symbol volumes for next file
            for k in symbol_volumes:
                symbol_volumes[k] = 0

        if not buckets:
            raise RuntimeError(
                f"No candles produced. current_symbol={state['current_symbol']} "
                f"symbols={self.symbols} vols={symbol_volumes} used={state['symbols_used']}"
            )

        self.symbols_used = state["symbols_used"]
        self.current_symbol = state["current_symbol"]

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
