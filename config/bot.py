from . import Settings
from typing import List

class BotSettings(Settings):
    auto: bool
    exclude_level: List[float]

    # TODO: support load_yaml

    @classmethod
    def set_bot_args(cls, parser):
        parser.add_argument(
            "--auto",
            action="store_true",
            help="Use automatically discovered levels; overrides any configured levels",
        )
        parser.add_argument(
            "--exclude-level",
            action="append",
            type=float,
            help="Price levels to ignore; useful with --auto",
        )
