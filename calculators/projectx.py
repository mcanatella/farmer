from core import calculate_levels_from_candles
from datetime import datetime, timedelta, timezone
from typing import Any

import math

class ProjectXCalculator:
    def __init__(
        self,
        market_data_client,
        contract_id,
        days=5,
        candle_length=5,
        unit="minutes",
        price_tolerance=5.0,
        min_separation=10,
        top_n=5,
    ):
        self.market_data_client = market_data_client
        self.contract_id = contract_id
        self.unit = 3 if unit == "hours" else 2
        self.days = days
        self.candle_length = candle_length
        self.price_tolerance = price_tolerance
        self.min_separation = min_separation
        self.top_n = top_n

        self.support_candidates = []
        self.resistance_candidates = []

        self.candles = None

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

    # Analyze the candle data to find support and resistance levels
    def calculate(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        self.poll()
        return calculate_levels_from_candles(self.candles, self.min_separation, self.price_tolerance, self.top_n)

    def poll(self):
        num_candles = math.ceil(60 / self.candle_length) * 24 * self.days
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=self.days)

        # Poll candles from server
        self.candles = self.market_data_client.bars(
            contractId=self.contract_id,
            live=False,
            startTime=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            endtime=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            unit=self.unit,
            unitNumber=self.candle_length,
            limit=num_candles,
            includePartialBar=False,
        )
