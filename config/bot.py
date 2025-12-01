from pydantic import BaseModel


class BotSettings(BaseModel):
    @classmethod
    def set_args(cls, parser):
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
