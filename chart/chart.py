from projectx_client import Auth, MarketData, Orders
from .signal_dispatcher import SignalDispatcher
from signalrcore.hub_connection_builder import HubConnectionBuilder
from .candle_poller import CandlePoller

import logging
import threading
import time as t


class Chart:
    def __init__(
        self,
        logger,
        market_hub_base,
        jwt_token,
        market_data_client,
        orders_client,
        account_id,
        contract_id,
        contract_size,
        levels=[],
    ):
        self.logger = logger
        self.market_hub_base = market_hub_base
        self.jwt_token = jwt_token
        self.account_id = account_id
        self.contract_id = contract_id
        self.contract_size = contract_size
        self.levels = levels

        self.position = None
        self.lock = threading.Lock()

        self.market_hub = (
            HubConnectionBuilder()
            .with_url(
                f"{self.market_hub_base}?access_token={self.jwt_token}",
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
        self.market_hub.on("GatewayQuote", self.on_quote)

        # Initialize ProjectX API clients
        self.market_data_client = market_data_client
        self.orders_client = orders_client

        # Initialize asynchronous historical data poller
        self.candle_poller = CandlePoller(
            self.logger, self.market_data_client, self.contract_id
        )

        # Initialize the buy / sell signal manager
        self.signal_dispatcher = SignalDispatcher(self.logger, levels=self.levels)

    # Main chart thread
    def start(self):
        self.market_hub.start()
        try:
            while True:
                t.sleep(1)
        except KeyboardInterrupt:
            self.logger.info(
                "user stopped market hub", extra={"event": "market_hub_stop"}
            )
            self.market_hub.send("UnsubscribeContractQuotes", [self.contract_id])
            self.market_hub.stop()

    # Candle poller start thread
    def start_candle_poller(self):
        self.candle_poller.start()

    def on_open(self):
        self.logger.info(
            "user opened connection to market hub",
            extra={"event": "market_hub_connect"},
        )

        # Subscribe to the configured futures contract
        self.market_hub.send("SubscribeContractQuotes", [self.contract_id])

        self.logger.info(
            f"subscribed to contract {self.contract_id}",
            extra={"event": "market_hub_subscribe"},
        )

    def on_close(self):
        self.logger.info(
            "user disconnected from market hub",
            extra={"event": "market_hub_disconnect"},
        )

    def on_quote(self, args):
        # Lock to prevent race conditions updating the signal dispatcher
        with self.lock:
            self.logger.debug(
                "received market quote",
                extra={"event": "market_hub_quote", "value": args},
            )

            # Abort if the chart is already monitoring an open position
            if self.position is not None:
                return

            # Read the latest price quote from the feed
            _, quote = args
            last_price = quote.get("lastPrice")
            if last_price is None:
                return

            # Check for a buy / sell signal using the latest price quote
            self.position = self.signal_dispatcher.check(last_price)

            # Abort if there is no signal
            if self.position is None:
                return

            # Unsubscribe from contract quotes while we manage our position
            self.market_hub.send("UnsubscribeContractQuotes", [self.contract_id])

            # Place a market order in the direction specified by position
            side = 0 if self.position["direction"] == "LONG" else 1

            # Initial market order
            self.orders_client.place(
                accountId=self.account_id,
                contractId=self.contract_id,
                type=2,
                side=side,
                size=self.contract_size,
            )

            # Place a limit order to take profit
            self.orders_client.place(
                accountId=self.account_id,
                contractId=self.contract_id,
                type=1,
                side=int(not side),
                size=self.contract_size,
                limitPrice=self.position["take_profit"],
            )

            # Place a stop order to cut losses
            self.orders_client.place(
                accountId=self.account_id,
                contractId=self.contract_id,
                type=4,
                side=int(not side),
                size=self.contract_size,
                stopPrice=self.position["stop_loss"],
            )

            # Now poll the status of orders until one is complete, then cancel the other
            # and re-subscribe to contract quotes.
            open_orders = self.orders_client.search_open(accountId=self.account_id)
            while len(open_orders) > 1:
                t.sleep(1)
                open_orders = self.orders_client.search_open(accountId=self.account_id)

            # Now cancel any remaining orders (we expect there to be only one though)
            for order in open_orders:
                self.orders_client.cancel(
                    accountId=self.account_id, orderId=order["id"]
                )

            # Unset our position as we no longer have any orders open
            self.position = None

            # Sleep for 1 minute after closing a position
            t.sleep(60)

            # Resume listening for quotes
            self.market_hub.send("SubscribeContractQuotes", [self.contract_id])
