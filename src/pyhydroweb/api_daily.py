"""Daily series acquisition from the legacy ANA WebService.

Python translation of hydroDataBR's ``R/ana-daily.R`` (hydrostat/hydroDataBR,
MIT).  The legacy ``HidroSerieHistorica`` route needs no authentication and
returns the monthly-wide XML parsed by :mod:`pyhydroweb.readers`.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from datetime import date
from typing import Optional, Union

import pandas as pd

from .contract import (
    filter_daily_variables,
    parse_ana_date,
    standardize_ana_daily_table,
)
from .exceptions import ApiRequestError, DataParsingError
from .http import LEGACY_BASE_URL, build_url, error_message_for_response, perform_get

#: Legacy route for daily historical series.
LEGACY_SERIES_PATH = "/HidroSerieHistorica"

#: variable -> (tipoDados, unit) on the legacy route.
LEGACY_VARIABLE_SPECS = {
    "stage": ("1", "cm"),
    "rainfall": ("2", "mm"),
    "discharge": ("3", "m3/s"),
}


def _format_legacy_date(value) -> Optional[str]:
    if value is None:
        return None
    parsed = parse_ana_date(value)
    if parsed is None:
        raise ValueError(f"Could not interpret date: {value!r}")
    return parsed.strftime("%d/%m/%Y")


def get_ana_daily_series(
    station_code: Union[str, int],
    variable: str,
    date_start: Union[str, date, None] = None,
    date_end: Union[str, date, None] = None,
    consistency_level: str = "2",
    base_url: str = LEGACY_BASE_URL,
    timeout: float = 60,
) -> pd.DataFrame:
    """Download one station's daily series from the legacy XML route.

    ``variable`` is one of ``"discharge"``, ``"stage"``, ``"rainfall"``;
    ``consistency_level`` is ``"1"`` (raw) or ``"2"`` (consisted).  Returns the
    standardized daily contract filtered to the requested variable.
    """
    if variable not in LEGACY_VARIABLE_SPECS:
        raise ValueError(
            f"variable must be one of {tuple(LEGACY_VARIABLE_SPECS)}; got {variable!r}"
        )
    consistency_level = str(consistency_level)
    if consistency_level not in {"1", "2"}:
        raise ValueError("consistency_level must be '1' or '2'.")
    data_type, _ = LEGACY_VARIABLE_SPECS[variable]
    query = {
        "codEstacao": str(station_code),
        "dataInicio": _format_legacy_date(date_start),
        "dataFim": _format_legacy_date(date_end),
        "tipoDados": data_type,
        "nivelConsistencia": consistency_level,
    }
    response = perform_get(
        url=build_url(base_url, LEGACY_SERIES_PATH, query),
        headers={"accept": "text/xml"},
        timeout=timeout,
    )
    if not 200 <= response["status"] < 300:
        raise ApiRequestError(
            error_message_for_response(
                response["status"],
                response["body"],
                "ANA legacy series request failed.",
            )
        )
    table = _series_table_from_xml_text(response["body"])
    out = standardize_ana_daily_table(
        table, source_label="ANA WebService XML", merge_consistency=True
    )
    return filter_daily_variables(out, [variable])


def _series_table_from_xml_text(text: str) -> pd.DataFrame:
    try:
        root = ET.parse(io.StringIO(text)).getroot()
    except ET.ParseError as exc:
        raise DataParsingError(
            f"Could not parse the legacy ANA XML response: {exc}"
        ) from None
    records = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "SerieHistorica":
            continue
        records.append(
            {child.tag.rsplit("}", 1)[-1]: child.text for child in element}
        )
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def get_ana_daily_discharge(station_code, start_date=None, end_date=None, **kwargs):
    """Daily discharge (m3/s) from the legacy route."""
    return get_ana_daily_series(
        station_code, "discharge", start_date, end_date, **kwargs
    )


def get_ana_daily_stage(station_code, start_date=None, end_date=None, **kwargs):
    """Daily stage (cm) from the legacy route."""
    return get_ana_daily_series(station_code, "stage", start_date, end_date, **kwargs)


def get_ana_daily_rainfall(station_code, start_date=None, end_date=None, **kwargs):
    """Daily rainfall (mm) from the legacy route."""
    return get_ana_daily_series(
        station_code, "rainfall", start_date, end_date, **kwargs
    )
