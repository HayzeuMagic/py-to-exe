"""Central logging configuration for PyForge.

Internal diagnostics go to a rotating log file in the app-data directory.
UI code should never print raw tracebacks to the user; it should log them
here and show a short, actionable message instead.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from utils.filesystem import app_logs_dir

_CONFIGURED = False


def configure_logging(verbose: bool = False) -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger("pyforge")

    if _CONFIGURED:
        logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        return logger

    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    log_file = app_logs_dir() / "pyforge.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    )
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console_handler)

    logger.propagate = False
    _CONFIGURED = True
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"pyforge.{name}")
