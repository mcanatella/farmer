import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from models import AggregationParams
from projectx_client import MarketData


class ProjectXAggregator:
    def __init__(
        self,
        logger: logging.Logger,
        params: AggregationParams,
        market_data_client: MarketData,
    ) -> None:
        if params.data_source.kind != "projectx":
            raise ValueError(
                f"Invalid data source for ProjectXAggregator: {params.data_source.kind}"
            )

        self.logger = logger
        self.market_data_client = market_data_client

        self.contract_id = params.data_source.contract_id
        self.days = params.lookback_days
        self.candle_length = params.candle_length

        if params.unit != "minutes":
            raise ValueError(f"Unsupported unit: {params.unit}")

        self.unit = 2

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
