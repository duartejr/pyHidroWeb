"""Utility functions for pyHidroWeb."""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


DATA_TYPE_NAMES: Dict[int, str] = {
    2: "rain_rate",
    3: "flow_rate",
}

DATA_TYPE_LONG_NAMES: Dict[int, str] = {
    2: "Rainfall",
    3: "Flow",
}

DATA_TYPE_UNITS: Dict[int, str] = {
    2: "mm$\\,$h$^{-1}$",
    3: "m$^3\\,$s$^{-1}$",
}

CONSISTENCY_LEVEL_NAMES: Dict[int, str] = {
    1: "Raw",
    2: "Consolidated",
}


def get_data_type_name(data_type: int) -> str:
    """Get the standardized name for a data type."""
    return DATA_TYPE_NAMES.get(data_type, "unknown")


def get_data_type_long_name(data_type: int) -> str:
    """Get the long name for a data type."""
    return DATA_TYPE_LONG_NAMES.get(data_type, "unknown")


def get_data_type_unit(data_type: int) -> str:
    """Get the unit for a data type."""
    return DATA_TYPE_UNITS.get(data_type, "")


def get_consistency_level_name(consistency_level: int) -> str:
    """Get the name for a consistency level."""
    return CONSISTENCY_LEVEL_NAMES.get(consistency_level, "unknown")
