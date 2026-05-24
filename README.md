# pyHidroWeb

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

A Python library for downloading Brazilian hydrological data from the HidroWeb portal of the National Water Agency (ANA).

## Features

- **Simple API**: Easy-to-use functions for downloading hydrological data
- **Multiple Data Types**: Support for both rainfall (precipitation) and flow (discharge) data
- **Flexible Output**: Export data as pandas DataFrame or xarray Dataset
- **Batch Downloads**: Download data for multiple stations at once
- **Shapefile Support**: Download data for all stations within a geographic area
- **Robust Error Handling**: Comprehensive exception handling and validation
- **Logging**: Built-in logging for debugging and monitoring
- **Type Hints**: Full type annotation for better code quality

## Installation

### Basic Installation

```bash
pip install pyhydroweb
```

### With Optional Dependencies

For xarray support:

```bash
pip install pyhydroweb[xarray]
```

For shapefile support:

```bash
pip install pyhydroweb[geopandas]
```

For all features:

```bash
pip install pyhydroweb[all]
```

### Development Installation

```bash
git clone https://github.com/duartejr/pyhidroweb.git
cd pyhidroweb
pip install -e ".[dev]"
```

## Quick Start

### Download Flow Data for a Single Station

```python
from pyhydroweb import download_hidroweb_data

# Download flow data for station 34879500
data = download_hidroweb_data(
    station=34879500,
    data_type=3,  # 3 for flow, 2 for rainfall
    output_format=0  # 0 for pandas DataFrame, 1 for xarray Dataset
)

print(data.head())
```

### Download with Date Range

```python
from pyhydroweb import download_hidroweb_data

# Download data for a specific date range
data = download_hidroweb_data(
    station=34879500,
    start_date="2020-01-01",
    end_date="2020-12-31",
    data_type=3,
    output_format=0
)
```

### Download for Multiple Stations

```python
from pyhydroweb import download_from_list

stations = ["34879500", "34880000", "34880100"]

download_from_list(
    stations_list=stations,
    path_dir="./hydro_data/",
    automatic_stations=True,
    data_type="vazoes"
)
```

### Download for Geographic Area (Shapefile)

```python
from pyhydroweb import download_from_shape

# Download data for all stations within a shapefile boundary
download_from_shape(
    shape="study_area.shp",
    path_dir="./hydro_data/",
    date_limits=["2020-01-01", "2020-12-31"]
)
```

## API Reference

### `download_hidroweb_data()`

Download hydrological data from HidroWeb API.

**Parameters:**

- `station` (int or str): Station code
- `start_date` (str, optional): Start date in YYYY-MM-DD format
- `end_date` (str, optional): End date in YYYY-MM-DD format
- `data_type` (int): Type of data
  - `2` = Rainfall (Chuva)
  - `3` = Flow (Vazão)
- `consistency_level` (int, optional): Data consistency
  - `1` = Raw data
  - `2` = Consolidated data
  - `0` = Both (default)
- `output_format` (int): Output format
  - `0` = pandas DataFrame
  - `1` = xarray Dataset (default)

**Returns:** pandas DataFrame or xarray Dataset

**Example:**

```python
data = download_hidroweb_data(
    station=34879500,
    start_date="2020-01-01",
    end_date="2020-12-31",
    data_type=3,
    consistency_level=2,
    output_format=1
)
```

### `download_from_list()`

Download data for multiple stations.

**Parameters:**

- `stations_list` (list): List of station codes
- `date_limits` (list, optional): [start_date, end_date]
- `path_dir` (str, optional): Directory to save CSV files
- `automatic_stations` (bool): Use automatic (True) or conventional (False) stations
- `data_type` (str): Data type ('vazoes' or 'cotas')
- `hidrologic_variable` (str): Variable type ('fluviometricas' or 'pluviometricas')

**Example:**

```python
download_from_list(
    stations_list=["34879500", "34880000"],
    date_limits=["2020-01-01", "2020-12-31"],
    path_dir="./data/",
    automatic_stations=True
)
```

### `download_from_shape()`

Download data for all stations within a shapefile boundary.

**Parameters:**

- `shape` (str): Path to shapefile
- `date_limits` (list, optional): [start_date, end_date]
- `path_dir` (str, optional): Directory to save CSV files
- `automatic_stations` (bool): Use automatic or conventional stations
- `data_type` (str): Data type
- `hidrologic_variable` (str): Variable type

**Example:**

```python
download_from_shape(
    shape="study_area.shp",
    date_limits=["2020-01-01", "2020-12-31"],
    path_dir="./data/",
    hidrologic_variable="fluviometricas"
)
```

## Error Handling

pyHidroWeb provides specific exceptions for different error scenarios:

```python
from pyhydroweb import (
    download_hidroweb_data,
    PyHidroWebError,
)
from pyhydroweb.exceptions import (
    InvalidDataTypeError,
    InvalidDateFormatError,
    DownloadError,
)

try:
    data = download_hidroweb_data(34879500, data_type=5)
except InvalidDataTypeError:
    print("Invalid data type. Use 2 for rainfall or 3 for flow.")
except DownloadError:
    print("Failed to download data from API.")
except PyHidroWebError as e:
    print(f"An error occurred: {e}")
```

## Logging

Enable logging to monitor operations:

```python
import logging
from pyhydroweb import setup_logging

# Set up logging
setup_logging(level=logging.DEBUG)

from pyhydroweb import download_hidroweb_data

data = download_hidroweb_data(34879500, data_type=3)
```

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/pyhydroweb --cov-report=html
```

## Station Codes

Station codes can be found on the [HidroWeb portal](https://www.snirh.gov.br/hidroweb/serieshistoricas).

Common station examples:

- 34879500 - Rio Paraná near Itaipu
- 34880000 - Rio Paraná de Campos
- 40006000 - Rio Araguaia

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## References

- [HidroWeb Portal](https://www.snirh.gov.br/hidroweb/)
- [National Water Agency (ANA)](https://www.gov.br/ana/)
- [ANA GitHub](https://github.com/anagovbr)

## Changelog

### Version 1.0.0

- Initial release
- Added `download_hidroweb_data()` for single station downloads
- Added `download_from_list()` for batch downloads
- Added `download_from_shape()` for geographic area downloads
- Comprehensive error handling and validation
- Full type hints and documentation
- Comprehensive test suite
