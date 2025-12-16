from datetime import datetime, timedelta, timezone
from projectx_client import MarketData
from typing import Any, Dict, List, Optional

import logging
import math


class ProjectXAggregator:
    def __init__(
        self,
        logger: logging.Logger,
        market_data_client: MarketData,
        contract_id: str,
        days: int,
        candle_length: int,  # TODO: Actually use this
        unit: Optional[str] = "minutes",  # TODO: Actually use this
    ) -> None:
        self.logger = logger
        self.market_data_client = market_data_client
        self.contract_id = contract_id

        self.days = days
        self.candle_length = candle_length
        self.unit = 3 if unit == "hours" else 2

        # TODO: Define candle type instead of using a Dict
        self.candles: List[Dict[str, Any]] = []

    def get_candles(self) -> List[Dict[str, Any]]:
        self._poll()

        return self.candles

    def _poll(self) -> None:
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
