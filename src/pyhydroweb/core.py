"""Core functionality for downloading and parsing hydrological data from HidroWeb."""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Union
import calendar

import requests
import pandas as pd

from .exceptions import (
    InvalidDataTypeError,
    InvalidOutputFormatError,
    DownloadError,
    DataParsingError,
    MissingDependencyError,
)
from .validators import (
    validate_data_type,
    validate_date_range,
    validate_output_format,
    validate_station_code,
)
from .utils import (
    get_data_type_name,
    get_data_type_unit,
)

logger = logging.getLogger(__name__)

# API Configuration
HIDROWEB_API_URL = "http://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica"


def extract_data(
    data: ET.Element, data_type: int
) -> Tuple[List[Optional[float]], List[int], List[datetime]]:
    """
    Extract hydrological data from XML response.

    Parses an XML structure containing historical series data and extracts values
    for either rainfall or flow, along with consistency levels and dates.

    Args:
        data: XML element containing the hydrological data
        data_type: Type of data (2 for rainfall, 3 for flow)

    Returns:
        Tuple containing:
        - list_data: Extracted values (float or None) for each day
        - list_consistency: Consistency levels for each value
        - list_month_dates: Datetime objects for each day

    Raises:
        InvalidDataTypeError: If data_type is not 2 or 3
        DataParsingError: If XML parsing fails
    """
    validate_data_type(data_type)

    list_data = []
    list_consistency = []
    list_month_dates = []

    try:
        for series in data.iter("SerieHistorica"):
            consistencia_elem = series.find("NivelConsistencia")
            date_elem = series.find("DataHora")

            if consistencia_elem is None or date_elem is None:
                logger.warning("Missing consistency or date element in XML data")
                continue

            consistencia = int(consistencia_elem.text)
            date_str = date_elem.text
            date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

            last_day = calendar.monthrange(date.year, date.month)[1]
            month_dates = [date + timedelta(days=k) for k in range(last_day)]

            for day in range(last_day):
                if data_type == 3:
                    field_name = f"Vazao{day + 1:02d}"
                elif data_type == 2:
                    field_name = f"Chuva{day + 1:02d}"

                value_elem = series.find(field_name)

                if value_elem is None or value_elem.text is None:
                    list_data.append(None)
                else:
                    try:
                        list_data.append(float(value_elem.text))
                    except ValueError:
                        list_data.append(None)
                        logger.debug(
                            f"Could not convert value to float: {value_elem.text}"
                        )

                list_consistency.append(consistencia)

            list_month_dates.extend(month_dates)

    except ET.ParseError as e:
        raise DataParsingError(f"Failed to parse XML data: {e}") from e
    except Exception as e:
        raise DataParsingError(f"Unexpected error during data extraction: {e}") from e

    return list_data, list_consistency, list_month_dates


def download_hidroweb_data(
    station: Union[int, str],
    start_date: str = "",
    end_date: str = "",
    data_type: int = 3,
    consistency_level: int = 0,
    output_format: int = 1,
) -> Union[pd.DataFrame, "xr.Dataset"]:
    """
    Download Brazilian hydrological data from HidroWeb API.

    Retrieves data from the National Water Agency (ANA) HidroWeb portal for
    a specified station, optionally filtered by date range and data type.

    Args:
        station: Station code (numeric ID)
        start_date: Start date in YYYY-MM-DD format. If empty, uses earliest available.
        end_date: End date in YYYY-MM-DD format. If empty, uses latest available.
        data_type: Type of data (2=Rainfall, 3=Flow). Default: 3
        consistency_level: Data consistency (1=Raw, 2=Consolidated, 0=Both). Default: 0
        output_format: Output format (0=DataFrame, 1=xarray Dataset). Default: 1

    Returns:
        Data in requested format (pandas DataFrame or xarray Dataset)

    Raises:
        InvalidDataTypeError: If data_type not in [2, 3]
        InvalidOutputFormatError: If output_format not in [0, 1]
        InvalidDateFormatError: If dates have invalid format
        DownloadError: If API request fails
        DataParsingError: If response parsing fails
        MissingDependencyError: If xarray is needed but not installed

    Example:
        >>> data = download_hidroweb_data(34879500, "2020-01-01", "2020-01-31", 3, 1)
    """
    validate_station_code(station)
    validate_data_type(data_type)
    validate_output_format(output_format)
    validate_date_range(start_date, end_date)

    logger.info(
        f"Downloading HidroWeb data for station {station}, "
        f"data_type={data_type}, period={start_date}:{end_date}"
    )

    params = {
        "codEstacao": station,
        "dataInicio": start_date,
        "dataFim": end_date,
        "tipoDados": data_type,
        "nivelConsistencia": consistency_level,
    }

    try:
        response = requests.get(HIDROWEB_API_URL, params=params, timeout=30)
        response.raise_for_status()
    except requests.exceptions.Timeout as e:
        raise DownloadError("API request timed out after 30 seconds") from e
    except requests.exceptions.ConnectionError as e:
        raise DownloadError(f"Failed to connect to HidroWeb API: {e}") from e
    except requests.exceptions.HTTPError as e:
        raise DownloadError(f"HTTP error from HidroWeb API: {e}") from e
    except requests.exceptions.RequestException as e:
        raise DownloadError(f"Failed to download data from API: {e}") from e

    try:
        tree = ET.ElementTree(ET.fromstring(response.content))
        root = tree.getroot()
    except ET.ParseError as e:
        raise DataParsingError(f"Failed to parse API response as XML: {e}") from e

    data, consistency, dates = extract_data(root, data_type)

    data_type_name = get_data_type_name(data_type)

    df = pd.DataFrame(
        {
            "time": dates,
            f"{data_type_name}_consistency_level": consistency,
            data_type_name: data,
        }
    )

    df = df.set_index("time")

    if output_format == 0:
        logger.debug("Returning pandas DataFrame")
        return df

    elif output_format == 1:
        try:
            import xarray as xr
        except ImportError as e:
            raise MissingDependencyError(
                "xarray is required for output_format=1. "
                "Install it with: pip install xarray"
            ) from e

        logger.debug("Converting to xarray Dataset")
        ds = df.to_xarray()
        ds[data_type_name].attrs["units"] = get_data_type_unit(data_type)
        ds[data_type_name].attrs["long_name"] = (
            data_type_name.replace("_", " ").title()
        )

        return ds
