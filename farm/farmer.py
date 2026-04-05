import logging
import time as t

from signalrcore.hub_connection_builder import HubConnectionBuilder

from aggregators import build_aggregator
from api.models import StrategyConfig
from strategies import build_strategy


class Farmer:
    def __init__(self, strategy_conf: StrategyConfig, logger: logging.Logger):
        if strategy_conf.aggregation_params.data_source.kind != "projectx":
            raise ValueError(
                f"Unsupported data source kind: {strategy_conf.aggregation_params.data_source.kind}"
            )

        self.strategy_conf = strategy_conf
        self.logger = logger

        self.aggregator = build_aggregator(strategy_conf, self.logger)
        self.strategy = build_strategy(self.strategy_conf, self.logger, self.aggregator.get_candles())

        # Aggregator should handle authentication on initialization and provide the jwt token
        self.jwt_token = self.aggregator.jwt_token

        self.market_hub = (
            HubConnectionBuilder()
            .with_url(
                f"{strategy_conf.aggregation_params.data_source.market_hub_base_url}?access_token={self.jwt_token}",
                options={
                    "access_token_factory": lambda: self.jwt_token,
                    "headers": {},
                    "verify_ssl": True,
                },
            )
            .configure_logging(logging.INFO)
            .with_automatic_reconnect(
                {
                    "type": "raw",
                    "keep_alive_interval": 10,
                    "reconnect_interval": 5,
                    "max_attempts": 5,
                }
            )
            .build()
        )

        # Register market hub handlers
        self.market_hub.on_open(self.on_open)
        self.market_hub.on_close(self.on_close)
        self.market_hub.on_error(self.on_error)
        self.market_hub.on("GatewayQuote", self.on_quote)

    def start(self):
        self.market_hub.start()
        try:
            while True:
                t.sleep(1)
        except KeyboardInterrupt:
            self.logger.info(
                "user stopped market hub", extra={"event": "market_hub_stop"}
            )
            self.market_hub.send("UnsubscribeContractQuotes", [self.strategy_conf.aggregation_params.data_source.contract_id])
            self.market_hub.stop()

    def on_open(self):
        self.logger.info(
            "user opened connection to market hub",
            extra={"event": "market_hub_connect"},
        )

        # Subscribe to the configured futures contract
        self.market_hub.send("SubscribeContractQuotes", [self.strategy_conf.aggregation_params.data_source.contract_id])

        self.logger.info(
            f"subscribed to contract {self.strategy_conf.aggregation_params.data_source.contract_id}",
            extra={"event": "market_hub_subscribe"},
        )

    def on_close(self):
        self.logger.info(
            "user disconnected from market hub",
            extra={"event": "market_hub_disconnect"},
        )

    def on_quote(self, args):
        self.logger.info(
            "received market quote",
            extra={"event": "market_hub_quote", "value": args},
        )

    def on_error(self, error):
        self.logger.error(
            "market hub error",
            extra={"event": "market_hub_error", "error": error.error},
        )
