"""Legacy pyHidroWeb API, kept as thin wrappers over the new modules.

.. deprecated:: 2.0
   Use :func:`pyhydroweb.get_ana_data` (or
   :func:`pyhydroweb.api_daily.get_ana_daily_series`) instead.  These wrappers
   exist so pre-2.0 scripts keep working; they now sit on top of the verified
   HTTPS legacy route and the standardized daily contract.

Notes on what changed in 2.0:

- the API URL moved from ``http://`` to ``https://telemetriaws1.ana.gov.br``;
- the previous ``EstacaoMetaDados`` metadata extraction was removed — that
  element does not exist in real ``HidroSerieHistorica`` responses (station
  metadata lives in the authenticated inventory route instead; see
  :func:`pyhydroweb.get_ana_stations` and the bundled inventory in
  :mod:`pyhydroweb.stations`).
"""

from __future__ import annotations

import logging
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional, Tuple, Union

import pandas as pd

from .api_daily import LEGACY_VARIABLE_SPECS, get_ana_daily_series
from .contract import standardize_ana_daily_table
from .exceptions import InvalidDataTypeError, MissingDependencyError
from .validators import (
    validate_data_type,
    validate_date_range,
    validate_output_format,
    validate_station_code,
)

logger = logging.getLogger(__name__)

# Kept for backward compatibility; the canonical constant now lives in
# pyhydroweb.http (LEGACY_BASE_URL) and uses HTTPS.
HIDROWEB_API_URL = (
    "https://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica"
)

_DATA_TYPE_VARIABLES = {2: "rainfall", 3: "discharge"}


def extract_data(
    data: ET.Element, data_type: int
) -> Tuple[List[Optional[float]], List[int], List[datetime], dict]:
    """Extract daily values from a legacy ``HidroSerieHistorica`` XML element.

    .. deprecated:: 2.0
       Use :func:`pyhydroweb.read_ana_xml` for files or
       :func:`pyhydroweb.get_ana_data` for downloads — both return the
       standardized daily contract.

    Returns ``(values, consistency_levels, dates, metadata)``.  ``metadata``
    is always an empty dict: the ``EstacaoMetaDados`` element previously
    parsed here does not exist in real ANA responses.
    """
    warnings.warn(
        "extract_data() is deprecated; use read_ana_xml()/get_ana_data() "
        "which return the standardized daily contract.",
        DeprecationWarning,
        stacklevel=2,
    )
    validate_data_type(data_type)
    variable = _DATA_TYPE_VARIABLES[data_type]

    records = []
    for element in data.iter():
        if element.tag.rsplit("}", 1)[-1] != "SerieHistorica":
            continue
        records.append(
            {child.tag.rsplit("}", 1)[-1]: child.text for child in element}
        )
    if not records:
        return [], [], [], {}
    table = standardize_ana_daily_table(
        pd.DataFrame(records), source_label="ANA WebService XML"
    )
    table = table[table["variable"] == variable]
    values = [None if pd.isna(value) else float(value) for value in table["value"]]
    consistency = [
        int(level) if level is not None and str(level).isdigit() else 0
        for level in table["consistency_level"]
    ]
    dates = [
        datetime(day.year, day.month, day.day) for day in table["date"]
    ]
    return values, consistency, dates, {}


def download_hidroweb_data(
    station_code: Union[str, int],
    start_date: str = "",
    end_date: str = "",
    data_type: int = 3,
    consistency_level: int = 2,
    output_format: int = 1,
    timeout: int = 30,
):
    """Download one station's daily series from the ANA legacy route.

    .. deprecated:: 2.0
       Use :func:`pyhydroweb.get_ana_data` instead.

    ``data_type``: 2 = rainfall, 3 = flow.  ``output_format``: 0 returns a
    pandas DataFrame, 1 returns an xarray Dataset (requires xarray).
    """
    warnings.warn(
        "download_hidroweb_data() is deprecated; use get_ana_data().",
        DeprecationWarning,
        stacklevel=2,
    )
    validate_station_code(station_code)
    validate_data_type(data_type)
    validate_output_format(output_format)
    validate_date_range(start_date, end_date)
    variable = _DATA_TYPE_VARIABLES[data_type]
    consistency = str(consistency_level) if consistency_level in (1, 2) else "2"

    daily = get_ana_daily_series(
        station_code,
        variable,
        date_start=start_date or None,
        date_end=end_date or None,
        consistency_level=consistency,
        timeout=timeout,
    )
    if daily.empty:
        logger.warning("No data returned for station %s.", station_code)
        return None

    column = "flow_rate" if variable == "discharge" else "precipitation"
    frame = pd.DataFrame(
        {
            column: daily["value"].to_numpy(),
            "consistency_level": daily["consistency_level"].to_numpy(),
        },
        index=pd.to_datetime(daily["date"]),
    )
    frame.index.name = "time"

    if output_format == 0:
        return frame

    try:
        import xarray as xr
    except ImportError:
        raise MissingDependencyError(
            "output_format=1 requires xarray (pip install pyhydroweb[xarray]); "
            "use output_format=0 for a pandas DataFrame."
        ) from None
    dataset = frame.to_xarray()
    _, unit = LEGACY_VARIABLE_SPECS[variable]
    dataset[column].attrs["units"] = (
        "m$\\,$s$^{-1}$" if variable == "discharge" else "mm"
    )
    dataset[column].attrs["long_name"] = (
        "Flow rate" if variable == "discharge" else "Precipitation"
    )
    dataset[column].attrs["source_unit"] = unit
    return dataset
