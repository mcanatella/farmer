from colorama import init, Style
from pythonjsonlogger import jsonlogger
from typing import Any

import logging


def init_backtest_logger():
    init(autoreset=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()

    # Set datefmt to only show down to seconds
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def init_strucutred_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def log_with_color(logger: Any, message: str, color: str, level: str) -> None:
    if level == "debug":
        logger.debug(f"{color}{message}{Style.RESET_ALL}")
    elif level == "warning":
        logger.warning(f"{color}{message}{Style.RESET_ALL}")
    elif level == "error":
        logger.error(f"{color}{message}{Style.RESET_ALL}")
    else:
        logger.info(f"{color}{message}{Style.RESET_ALL}")
