# API Reference

Complete API documentation for pyHidroWeb.

## Core Module (`pyhydroweb.core`)

### `download_hidroweb_data()`

Download Brazilian hydrological data from HidroWeb API.

```python
download_hidroweb_data(
    station: Union[int, str],
    start_date: str = "",
    end_date: str = "",
    data_type: int = 3,
    consistency_level: int = 0,
    output_format: int = 1
) -> Union[pd.DataFrame, xr.Dataset]
```

**Parameters:**

- **station** (int or str): Station code for which to download data
- **start_date** (str, optional): Start date in YYYY-MM-DD format. If empty, uses earliest available data.
- **end_date** (str, optional): End date in YYYY-MM-DD format. If empty, uses latest available data.
- **data_type** (int, default=3): Type of hydrological data to download
  - `2`: Rainfall (Chuva) in mm/h
  - `3`: Flow/Discharge (Vazão) in m³/s
- **consistency_level** (int, default=0): Level of data quality/consistency
  - `0`: Both raw and consolidated (default)
  - `1`: Raw data only (automatically measured)
  - `2`: Consolidated data only (verified/corrected)
- **output_format** (int, default=1): Output data structure
  - `0`: pandas DataFrame
  - `1`: xarray Dataset (recommended)

**Returns:**

- `pd.DataFrame` (if output_format=0): Indexed by date with columns:
  - `{variable}_consistency_level`: Data consistency level
  - `{variable}`: The actual data values
- `xr.Dataset` (if output_format=1): xarray Dataset with proper metadata and attributes

**Raises:**

- `InvalidDataTypeError`: If data_type not in [2, 3]
- `InvalidOutputFormatError`: If output_format not in [0, 1]
- `InvalidDateFormatError`: If dates don't match YYYY-MM-DD format
- `InvalidDateRangeError`: If start_date > end_date
- `DownloadError`: If API request fails
- `DataParsingError`: If response parsing fails
- `MissingDependencyError`: If xarray required but not installed

**Examples:**

```python
# Download flow data as DataFrame
df = download_hidroweb_data(34879500, data_type=3, output_format=0)

# Download rainfall data as xarray
ds = download_hidroweb_data(
    34879500,
    start_date="2020-01-01",
    end_date="2020-12-31",
    data_type=2,
    consistency_level=2,
    output_format=1
)

# Download all data types
df = download_hidroweb_data(
    34879500,
    consistency_level=0,  # Both raw and consolidated
    output_format=0
)
```

### `extract_data()`

Extract hydrological data from XML response element.

```python
extract_data(
    data: ET.Element,
    data_type: int
) -> Tuple[List[Optional[float]], List[int], List[datetime]]
```

**Parameters:**

- **data** (ET.Element): XML element containing the hydrological data
- **data_type** (int): Type of data (2=rainfall, 3=flow)

**Returns:**

Tuple of:
- **list_data** (List[Optional[float]]): Extracted values for each day (None for missing)
- **list_consistency** (List[int]): Consistency levels for each value
- **list_month_dates** (List[datetime]): Date objects for each day

**Raises:**

- `InvalidDataTypeError`: If data_type not in [2, 3]
- `DataParsingError`: If XML parsing fails

**Example:**

```python
import xml.etree.ElementTree as ET
from pyhydroweb.core import extract_data

root = ET.fromstring(xml_response)
values, consistency, dates = extract_data(root, data_type=3)
```

---

## Downloaders Module (`pyhydroweb.downloaders`)

### `download_from_list()`

Download hydrological data for multiple stations.

```python
download_from_list(
    stations_list: List[str],
    date_limits: Optional[List[str]] = None,
    path_dir: Optional[str] = None,
    automatic_stations: bool = True,
    data_type: str = "vazoes",
    hidrologic_variable: str = "fluviometricas"
) -> None
```

**Parameters:**

- **stations_list** (List[str]): List of station codes to download
- **date_limits** (List[str], optional): List with [start_date, end_date] to filter data. Format: YYYY-MM-DD
- **path_dir** (str, optional): Directory to save CSV files. If None, uses current directory.
- **automatic_stations** (bool, default=True): 
  - `True`: Download from automatic stations (recent data from 2023+)
  - `False`: Download from conventional stations (historical data)
- **data_type** (str, default="vazoes"): Type of data for conventional stations
  - `"vazoes"`: Flow/discharge data
  - `"cotas"`: Water level data
- **hidrologic_variable** (str, default="fluviometricas"): Variable type
  - `"fluviometricas"`: Fluviometric (river) stations
  - `"pluviometricas"`: Pluviometric (rainfall) stations

**Raises:**

- `ValueError`: If stations_list is empty
- `DownloadError`: If download fails
- `FileNotFoundError`: If output directory cannot be created

**Examples:**

```python
# Download automatic station data
download_from_list(
    ["34879500", "34880000"],
    path_dir="./data/"
)

# Download conventional station data with date range
download_from_list(
    ["34879500", "34880000"],
    date_limits=["2010-01-01", "2020-12-31"],
    path_dir="./data/",
    automatic_stations=False,
    hidrologic_variable="fluviometricas",
    data_type="vazoes"
)
```

### `download_from_shape()`

Download hydrological data for all stations within a geographic area.

```python
download_from_shape(
    shape: str,
    date_limits: Optional[List[str]] = None,
    path_dir: Optional[str] = None,
    automatic_stations: bool = True,
    data_type: str = "vazoes",
    hidrologic_variable: str = "fluviometricas"
) -> None
```

**Parameters:**

- **shape** (str): Path to shapefile (.shp) defining the study area
- **date_limits** (List[str], optional): List with [start_date, end_date] in YYYY-MM-DD format
- **path_dir** (str, optional): Directory to save CSV files. If None, uses current directory.
- **automatic_stations** (bool, default=True): Use automatic or conventional stations
- **data_type** (str, default="vazoes"): Type of data ('vazoes' or 'cotas')
- **hidrologic_variable** (str, default="fluviometricas"): Variable type

**Raises:**

- `MissingDependencyError`: If geopandas is not installed
- `FileNotFoundError`: If shapefile doesn't exist or cannot be read
- `DownloadError`: If data download fails

**Examples:**

```python
# Download data for all stations in a study area
download_from_shape(
    "study_area.shp",
    path_dir="./data/"
)

# With date range and date filtering
download_from_shape(
    "amazon_basin.shp",
    date_limits=["2015-01-01", "2020-12-31"],
    path_dir="./amazon_data/",
    automatic_stations=False
)
```

---

## Validators Module (`pyhydroweb.validators`)

### `validate_date_format()`

Validate and parse a date string.

```python
validate_date_format(
    date_string: str,
    format_str: str = "%Y-%m-%d"
) -> Optional[datetime]
```

### `validate_date_range()`

Validate a date range.

```python
validate_date_range(
    start_date: Optional[str],
    end_date: Optional[str]
) -> Tuple[Optional[datetime], Optional[datetime]]
```

### `validate_data_type()`

Validate data type parameter.

```python
validate_data_type(data_type: int) -> None
```

### `validate_station_code()`

Validate station code.

```python
validate_station_code(station_code: Union[int, str]) -> None
```

### `validate_output_format()`

Validate output format parameter.

```python
validate_output_format(output_format: int) -> None
```

---

## Exceptions Module (`pyhydroweb.exceptions`)

### Exception Hierarchy

```
PyHidroWebError (base)
├── InvalidDataTypeError
├── InvalidDateFormatError
├── InvalidDateRangeError
├── InvalidStationCodeError
├── InvalidOutputFormatError
├── DownloadError
├── DataParsingError
└── MissingDependencyError
```

### Exception Usage

```python
from pyhydroweb import download_hidroweb_data
from pyhydroweb.exceptions import (
    InvalidDataTypeError,
    DownloadError,
    PyHidroWebError
)

try:
    data = download_hidroweb_data(34879500, data_type=5)
except InvalidDataTypeError as e:
    print(f"Invalid data type: {e}")
except DownloadError as e:
    print(f"Download failed: {e}")
except PyHidroWebError as e:
    print(f"Other error: {e}")
```

---

## Logging

### `setup_logging()`

Configure logging for pyHidroWeb.

```python
from pyhydroweb import setup_logging
import logging

# Enable DEBUG level logging
setup_logging(level=logging.DEBUG)

# Default is INFO level
setup_logging()

# Disable logging
setup_logging(level=logging.WARNING)
```

---

## Data Type Reference

### Rainfall Data (data_type=2)

- **Units**: mm/h
- **Column Name**: `rain_rate`
- **Consistency Level**: Data quality indicator
- **XML Field Names**: `Chuva01` to `Chuva31` (daily values)

### Flow Data (data_type=3)

- **Units**: m³/s
- **Column Name**: `flow_rate`
- **Consistency Level**: Data quality indicator
- **XML Field Names**: `Vazao01` to `Vazao31` (daily values)

### Consistency Levels

- **0**: Both raw and consolidated data (used as parameter)
- **1**: Raw data (automatically measured without manual verification)
- **2**: Consolidated data (verified and possibly corrected by specialists)

---

## Station Code Reference

Station codes are numeric identifiers assigned by ANA (National Water Agency).

Find station codes at: https://www.snirh.gov.br/hidroweb/serieshistoricas

Common examples:

| Code | Station Name | State | Type |
|------|--------------|-------|------|
| 34879500 | Rio Paraná near Itaipu | PR | Fluviometric |
| 34880000 | Rio Paraná de Campos | SP | Fluviometric |
| 40006000 | Rio Araguaia | MT | Fluviometric |
