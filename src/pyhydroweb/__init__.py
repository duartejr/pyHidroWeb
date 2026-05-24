"""pyHidroWeb - Download Brazilian hydrological data from HidroWeb."""

import logging

from .core import download_hidroweb_data, extract_data
from .downloaders import download_from_list, download_from_shape
from .exceptions import PyHidroWebError
from .logging_config import setup_logging

__version__ = "1.0.0"
__author__ = "pyHidroWeb Contributors"

__all__ = [
    "download_hidroweb_data",
    "extract_data",
    "download_from_list",
    "download_from_shape",
    "PyHidroWebError",
    "setup_logging",
]

# Configure logging by default
logging.getLogger(__name__).addHandler(logging.NullHandler())
