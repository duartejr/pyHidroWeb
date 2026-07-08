"""Table dispatcher over daily data, analyses and diagnostics.

Python translation of hydroDataBR's ``R/tables.R`` and the table dispatcher in
``R/hydro-output.R`` (hydrostat/hydroDataBR, MIT).
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .analysis import ANALYSES, analyze_hydro_data, extract_daily_data
from .cross_sections import table_cross_sections
from .internal_data import load_ana_stations

TABLES = ANALYSES + ("station_products", "request_report", "cross_sections")

_STATION_PRODUCT_COLUMNS = {
    "daily_discharge": ("discharge_start_date", "discharge_end_date"),
    "daily_stage": ("stage_start_date", "stage_end_date"),
    "daily_rainfall": ("rainfall_start_date", "rainfall_end_date"),
    "telemetry": ("telemetric_start_date", "telemetric_end_date"),
}


def table_station_products(
    stations: Optional[pd.DataFrame] = None, station_code=None
) -> pd.DataFrame:
    """Long table of product availability per station from the inventory."""
    table = stations if stations is not None else load_ana_stations()
    if station_code is not None:
        codes = (
            [str(code) for code in station_code]
            if isinstance(station_code, (list, tuple, set))
            else [str(station_code)]
        )
        table = table[table["station_code"].astype(str).isin(codes)]
    rows = []
    for _, station in table.iterrows():
        for product, (start_column, end_column) in _STATION_PRODUCT_COLUMNS.items():
            start = station.get(start_column)
            end = station.get(end_column)
            available = bool(
                (pd.notna(start) and str(start).strip())
                or (pd.notna(end) and str(end).strip())
            )
            rows.append(
                {
                    "station_code": station.get("station_code"),
                    "station_name": station.get("station_name"),
                    "product": product,
                    "available": available,
                    "start_date": start,
                    "end_date": end,
                }
            )
        rows.append(
            {
                "station_code": station.get("station_code"),
                "station_name": station.get("station_name"),
                "product": "discharge_measurements",
                "available": bool(station.get("has_discharge_measurements")),
                "start_date": None,
                "end_date": None,
            }
        )
    return pd.DataFrame(rows)


def table_request_report(report) -> pd.DataFrame:
    """Normalize an acquisition request report (accepts the batch dict too)."""
    if isinstance(report, dict) and "request_report" in report:
        report = report["request_report"]
    if not isinstance(report, pd.DataFrame):
        raise TypeError("report must be a DataFrame or a get_ana_data_batch result.")
    preferred = ["station_code", "status", "success", "n_rows", "message"]
    columns = [column for column in preferred if column in report.columns] + [
        column for column in report.columns if column not in preferred
    ]
    return report[columns].reset_index(drop=True)


def table_hydro_data(
    data,
    table: str,
    variable: Optional[str] = None,
    station_code=None,
    period: Optional[str] = None,
    **kwargs,
) -> pd.DataFrame:
    """Source-neutral table dispatcher (mirrors hydroDataBR's).

    ``table`` accepts every analysis name from
    :func:`pyhydroweb.analysis.analyze_hydro_data` plus ``station_products``,
    ``request_report`` and ``cross_sections``.
    """
    name = str(table).strip().lower().replace("-", "_")
    if name not in TABLES:
        raise ValueError(f"Unknown table {table!r}. Valid tables: {', '.join(TABLES)}.")
    if name == "station_products":
        stations = data if isinstance(data, pd.DataFrame) else None
        return table_station_products(stations, station_code=station_code)
    if name == "request_report":
        return table_request_report(data)
    if name == "cross_sections":
        return table_cross_sections(
            data, station_code=station_code, level=kwargs.pop("level", "sections")
        )
    analysis_kwargs = dict(kwargs)
    if period is not None:
        analysis_kwargs["period"] = period
    return analyze_hydro_data(
        data, name, variable=variable, station_code=station_code, **analysis_kwargs
    )
