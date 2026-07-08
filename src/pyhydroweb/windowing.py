"""Date-window planning for the ANA HidroWebService.

Python translation of hydroDataBR's ``R/ana-api-windowing.R`` (hydrostat/
hydroDataBR, MIT).  The specialized routes of the authenticated API reject
requests spanning more than 366 days, so long ranges must be split.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Tuple, Union

from .contract import parse_ana_date
from .exceptions import ApiWindowError

#: Maximum window accepted by the specialized API routes.
API_MAX_WINDOW_DAYS = 366


def as_date_scalar(value, arg: str = "date") -> date:
    """Coerce a single value to :class:`datetime.date` or raise."""
    parsed = parse_ana_date(value)
    if parsed is None:
        raise ValueError(f"{arg} could not be interpreted as a date: {value!r}")
    return parsed


def window_n_days(start_date: Union[str, date], end_date: Union[str, date]) -> int:
    """Number of days in the inclusive window [start_date, end_date]."""
    start = as_date_scalar(start_date, "start_date")
    end = as_date_scalar(end_date, "end_date")
    return (end - start).days + 1


def assert_api_window(
    start_date: Union[str, date],
    end_date: Union[str, date],
    max_days: int = API_MAX_WINDOW_DAYS,
) -> None:
    """Raise :class:`ApiWindowError` when the window is empty or too long."""
    n_days = window_n_days(start_date, end_date)
    if n_days < 1:
        raise ApiWindowError("start_date must not be after end_date.")
    if n_days > max_days:
        raise ApiWindowError(
            f"The requested window spans {n_days} days, above the API limit of "
            f"{max_days}. Split it with split_api_windows()."
        )


def split_api_windows(
    start_date: Union[str, date],
    end_date: Union[str, date],
    max_days: int = API_MAX_WINDOW_DAYS,
) -> List[Tuple[date, date]]:
    """Split [start_date, end_date] into consecutive windows of <= max_days."""
    start = as_date_scalar(start_date, "start_date")
    end = as_date_scalar(end_date, "end_date")
    if start > end:
        raise ApiWindowError("start_date must not be after end_date.")
    windows = []
    current = start
    while current <= end:
        current_end = min(current + timedelta(days=max_days - 1), end)
        windows.append((current, current_end))
        current = current_end + timedelta(days=1)
    return windows


def one_year_windows(
    start_date: Union[str, date], end_date: Union[str, date]
) -> List[Tuple[date, date]]:
    """Split [start_date, end_date] into 1-calendar-year steps.

    Mirrors ``ana_api_one_year_windows``: each window advances one year from
    its start, clipped to ``end_date``.
    """
    start = as_date_scalar(start_date, "start_date")
    end = as_date_scalar(end_date, "end_date")
    if start > end:
        raise ApiWindowError("start_date must not be after end_date.")
    windows = []
    current = start
    while current <= end:
        try:
            next_start = current.replace(year=current.year + 1)
        except ValueError:  # February 29th
            next_start = current.replace(year=current.year + 1, day=28)
        window_end = min(next_start - timedelta(days=1), end)
        windows.append((current, window_end))
        current = window_end + timedelta(days=1)
    return windows
