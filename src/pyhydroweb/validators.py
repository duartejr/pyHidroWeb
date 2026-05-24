"""Input validation utilities for pyHidroWeb."""

from datetime import datetime
from typing import Optional, Tuple
from .exceptions import (
    InvalidDataTypeError,
    InvalidDateFormatError,
    InvalidDateRangeError,
    InvalidStationCodeError,
    InvalidOutputFormatError,
)


def validate_date_format(date_string: str, format_str: str = "%Y-%m-%d") -> datetime:
    """
    Validate and parse a date string.

    Args:
        date_string: Date string to validate
        format_str: Expected date format (default: "%Y-%m-%d")

    Returns:
        Parsed datetime object

    Raises:
        InvalidDateFormatError: If date string doesn't match expected format
    """
    if not date_string or not isinstance(date_string, str):
        return None

    try:
        return datetime.strptime(date_string, format_str)
    except ValueError as e:
        raise InvalidDateFormatError(
            f"Invalid date format '{date_string}'. Expected format: {format_str}"
        ) from e


def validate_date_range(
    start_date: Optional[str], end_date: Optional[str]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Validate and parse a date range.

    Args:
        start_date: Start date string or None
        end_date: End date string or None

    Returns:
        Tuple of (start_datetime, end_datetime)

    Raises:
        InvalidDateFormatError: If dates don't match expected format
        InvalidDateRangeError: If start_date > end_date
    """
    start_dt = validate_date_format(start_date) if start_date else None
    end_dt = validate_date_format(end_date) if end_date else None

    if start_dt and end_dt and start_dt > end_dt:
        raise InvalidDateRangeError(
            f"Start date ({start_date}) cannot be after end date ({end_date})"
        )

    return start_dt, end_dt


def validate_data_type(data_type: int) -> None:
    """
    Validate data type parameter.

    Args:
        data_type: Type code (2 for rainfall, 3 for flow)

    Raises:
        InvalidDataTypeError: If data_type is not 2 or 3
    """
    if data_type not in [2, 3]:
        raise InvalidDataTypeError(
            f"Invalid data type {data_type}. Use 2 for Rainfall or 3 for Flow."
        )


def validate_consistency_level(consistency_level: int) -> None:
    """
    Validate consistency level parameter.

    Args:
        consistency_level: Consistency level code (1 for raw, 2 for consolidated)

    Raises:
        InvalidDataTypeError: If consistency_level is not valid
    """
    if consistency_level and consistency_level not in [1, 2]:
        raise InvalidDataTypeError(
            f"Invalid consistency level {consistency_level}. "
            "Use 1 for Raw or 2 for Consolidated data."
        )


def validate_station_code(station_code) -> None:
    """
    Validate station code parameter.

    Args:
        station_code: Station code (should be numeric)

    Raises:
        InvalidStationCodeError: If station code is invalid
    """
    if not station_code:
        raise InvalidStationCodeError("Station code cannot be empty")

    try:
        int(station_code)
    except (ValueError, TypeError) as e:
        raise InvalidStationCodeError(
            f"Invalid station code '{station_code}'. Must be numeric."
        ) from e


def validate_output_format(output_format: int) -> None:
    """
    Validate output format parameter.

    Args:
        output_format: Format code (0 for DataFrame, 1 for xarray Dataset)

    Raises:
        InvalidOutputFormatError: If output_format is not valid
    """
    if output_format not in [0, 1]:
        raise InvalidOutputFormatError(
            f"Invalid output format {output_format}. "
            "Use 0 for pandas DataFrame or 1 for xarray Dataset."
        )
