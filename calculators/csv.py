from core import calculate_levels_from_candles, run_engine, Tick
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
from tickers import CsvTicker

import logging
import re

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


class CsvCalculator:
    def __init__(
        self,
        logger: logging.Logger,
        data_dir: str | Path,
        start_date: date,
        end_date: date,
        symbols: List[str],
        candle_length: Optional[int] = 5,
        unit: Optional[str] = "minutes",
        price_tolerance: Optional[float] = 5.0,
        min_separation: Optional[int] = 10,
        top_n: Optional[int] = 5,
    ):
        self.logger = logger
        self.data_dir = Path(data_dir)
        self.start_date = start_date
        self.end_date = end_date

        self.symbols = symbols
        self.start_symbol = self.symbols[0]

        self.unit = 3 if unit == "hours" else 2
        self.candle_length = candle_length
        self.price_tolerance = price_tolerance
        self.min_separation = min_separation
        self.top_n = top_n

        self.candles: List[Dict[str, Any]] = []

    def calculate_and_print(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        top_support, top_resistance = self.calculate()

        print("\nTop Support Levels:")
        for lvl in top_support:
            print(
                f"  Level: {lvl['price']:.2f} | Hits: {len(lvl['hits'])} | Score: {lvl['score']:.2f}"
            )

        print("\nTop Resistance Levels:")
        for lvl in top_resistance:
            print(
                f"  Level: {lvl['price']:.2f} | Hits: {len(lvl['hits'])} | Score: {lvl['score']:.2f}"
            )

        return top_support, top_resistance

    def calculate(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        self.poll()
        return calculate_levels_from_candles(
            self.candles, self.min_separation, self.price_tolerance, self.top_n
        )

    def poll(self) -> None:
        # OHLCV state accumulator keyed by (bucket_ts, symbol)
        buckets: Dict[tuple[datetime, str], Dict[str, float]] = {}

        symbol_volumes: Dict[str, int] = {self.start_symbol: 0}
        for sym in self.symbols:
            symbol_volumes[sym] = 0

        current_symbol = self.start_symbol

        def handler(tick: Tick):
            nonlocal buckets, symbol_volumes, current_symbol

            symbol_volumes[tick.symbol] += tick.size
            if (
                tick.symbol != current_symbol
                and symbol_volumes[tick.symbol] > symbol_volumes[current_symbol]
            ):
                # Rollover to the next contract symbol when its volume exceeds the current one
                self.logger.info(
                    f"Switching from {current_symbol} to {tick.symbol} at {tick.t.isoformat()} with volumes: {symbol_volumes}"
                )
                current_symbol = tick.symbol

            if tick.symbol != current_symbol:
                return

            bkt = _floor_5min(tick.t), tick.symbol
            rec = buckets.get(bkt)
            if rec is None:
                # open=first price, high/low init to price, close updates, volume sums
                buckets[bkt] = {
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

        # Collect matching files by filename date
        files: List[Path] = []
        for p in sorted(self.data_dir.glob("glbx-mdp3-*.trades.csv")):
            m = FNAME_RE.search(p.name)
            if not m:
                continue
            d = _parse_yyyymmdd(m.group(1))
            if self.start_date <= d <= self.end_date:
                files.append(p)

        for fp in files:
            ticker = CsvTicker(fp, self.symbols)

            run_engine(ticker, handler)

            # Reset symbol volumes for next file
            for k in symbol_volumes:
                symbol_volumes[k] = 0

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
