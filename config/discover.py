from . import Settings


class DiscoverSettings(Settings):
    @classmethod
    def set_args(cls, parser):
        parser.add_argument(
            "--contract-id",
            required=True,
            type=str,
            help="The the contract id to analyze",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=10,
            help="The number of days back (from now) to analyze",
        )
        parser.add_argument(
            "--candle-length", type=int, default=5, help="The candle timeframe"
        )
        parser.add_argument(
            "--unit",
            type=str,
            default="minutes",
            help="The unit used to measure the candle length; only minutes or hours supported",
        )
        parser.add_argument(
            "--price-tolerance",
            type=float,
            default=0.05,
            help="Price range within which levels are considered the same",
        )
        parser.add_argument(
            "--min-separation",
            type=int,
            default=10,
            help="Number of candles before/after to consider a high/low isolated",
        )
        parser.add_argument(
            "--top-n",
            type=int,
            default=5,
            help="Number of support/resistance levels to return",
        )
