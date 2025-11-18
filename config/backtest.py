from . import Settings

class BacktestSettings(Settings):
    backtest_date: str
    data_dir: str

    # TODO: support load_yaml

    @classmethod
    def set_args(cls, parser):
        parser.add_argument(
            "--backtest-date",
            type=str,
            default="20250827",
            help="The date to backtest",
        )
        parser.add_argument(
            "--data-dir",
            type=str,
            default="cl_historical",
            help="Specifies the data directory containing tick data files",
        )
