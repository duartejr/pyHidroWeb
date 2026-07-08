"""Station filtering over the bundled ANA inventory.

Python translation of hydroDataBR's ``R/filter-stations.R`` (hydrostat/
hydroDataBR, MIT).  Filters operate on the June-2026 snapshot by default but
accept any DataFrame with the same columns (e.g. a live
:func:`pyhydroweb.api_inventory.get_ana_stations` result).
"""

from __future__ import annotations

import re
from typing import Optional, Sequence, Union

import pandas as pd

from .internal_data import load_ana_stations

#: Products understood by the ``product`` filter.
STATION_PRODUCTS = (
    "discharge",
    "stage",
    "rainfall",
    "telemetry",
    "discharge_measurements",
)

_PRODUCT_DATE_COLUMNS = {
    "discharge": ("discharge_start_date", "discharge_end_date"),
    "stage": ("stage_start_date", "stage_end_date"),
    "rainfall": ("rainfall_start_date", "rainfall_end_date"),
    "telemetry": ("telemetric_start_date", "telemetric_end_date"),
}
_PRODUCT_FLAG_COLUMNS = {
    "stage": "has_stage_data",
    "rainfall": "has_rainfall_data",
    "telemetry": "has_telemetry",
    "discharge_measurements": "has_discharge_measurements",
}


def _non_empty(series: pd.Series) -> pd.Series:
    return series.notna() & (series.astype(str).str.strip() != "")


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def station_has_product(stations: pd.DataFrame, product: str) -> pd.Series:
    """Boolean mask of stations offering ``product``.

    Boolean ``has_*`` flags are used when present; otherwise availability is
    inferred from non-empty product start/end dates.
    """
    if product not in STATION_PRODUCTS:
        raise ValueError(
            f"product must be one of {STATION_PRODUCTS}; got {product!r}"
        )
    flag_column = _PRODUCT_FLAG_COLUMNS.get(product)
    if flag_column and flag_column in stations.columns:
        return stations[flag_column].fillna(False).astype(bool)
    if product == "discharge_measurements":
        raise ValueError(
            "The station table has no has_discharge_measurements column."
        )
    start_column, end_column = _PRODUCT_DATE_COLUMNS[product]
    for column in (start_column, end_column):
        if column not in stations.columns:
            raise ValueError(f"The station table has no {column} column.")
    return _non_empty(stations[start_column]) | _non_empty(stations[end_column])


def filter_ana_stations(
    station_data: Optional[pd.DataFrame] = None,
    station_code=None,
    state_code=None,
    municipality=None,
    station_type=None,
    basin_code=None,
    name_pattern: Optional[str] = None,
    product: Union[str, Sequence[str], None] = None,
    is_operating: Optional[bool] = None,
) -> pd.DataFrame:
    """Filter the ANA station inventory.

    All criteria are combined with AND.  ``name_pattern`` is a case-insensitive
    regular expression applied to ``station_name``; ``product`` accepts one or
    more of ``discharge``, ``stage``, ``rainfall``, ``telemetry``,
    ``discharge_measurements``.
    """
    stations = station_data if station_data is not None else load_ana_stations()
    if not isinstance(stations, pd.DataFrame):
        raise TypeError("station_data must be a pandas DataFrame.")
    mask = pd.Series(True, index=stations.index)

    def require(column: str) -> pd.Series:
        if column not in stations.columns:
            raise ValueError(f"The station table has no {column} column.")
        return stations[column]

    codes = [str(code) for code in _as_list(station_code)]
    if codes:
        mask &= require("station_code").astype(str).isin(codes)
    states = [str(code).upper() for code in _as_list(state_code)]
    if states:
        mask &= require("state_code").astype(str).str.upper().isin(states)
    municipalities = [str(name).upper() for name in _as_list(municipality)]
    if municipalities:
        mask &= require("municipality").astype(str).str.upper().isin(municipalities)
    types = [str(name).upper() for name in _as_list(station_type)]
    if types:
        mask &= require("station_type").astype(str).str.upper().isin(types)
    basins = [str(code) for code in _as_list(basin_code)]
    if basins:
        mask &= require("basin_code").astype(str).isin(basins)
    if name_pattern is not None:
        names = require("station_name").astype(str)
        pattern = re.compile(name_pattern, re.IGNORECASE)
        mask &= names.map(lambda name: bool(pattern.search(name)))
    if is_operating is not None:
        mask &= require("is_operating").fillna(False).astype(bool) == bool(is_operating)
    for item in _as_list(product):
        mask &= station_has_product(stations, str(item))
    return stations[mask].reset_index(drop=True)
