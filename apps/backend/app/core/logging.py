"""Central logging configuration (console + rotating file)."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_LOGGER_NAME = "ai_drama_ide"


def setup_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    logger = logging.getLogger(APP_LOGGER_NAME)
    if logger.handlers:
        return
    logger.setLevel(level.upper())
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    logger.propagate = False


def get_logger(name: str = "") -> logging.Logger:
    return logging.getLogger(APP_LOGGER_NAME + (f".{name}" if name else ""))
