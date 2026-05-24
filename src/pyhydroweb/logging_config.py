"""Logging configuration for pyHidroWeb."""

import logging


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure logging for pyHidroWeb.

    Args:
        level: Logging level (default: logging.INFO)
    """
    logger = logging.getLogger("pyhydroweb")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
