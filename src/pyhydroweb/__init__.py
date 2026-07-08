"""pyHidroWeb — acquire, standardize, analyze and export Brazilian
hydrological data from ANA (Agência Nacional de Águas e Saneamento Básico).

The public API mirrors the hydroDataBR R package (hydrostat/hydroDataBR, MIT),
of which this package is a Python translation:

- Authentication: :func:`ana_authenticate`
- Acquisition: :func:`get_ana_data`, :func:`get_ana_data_batch`,
  :func:`get_ana_stations`, :func:`download_ana_cross_section_vertices`
- Local readers: :func:`read_ana_xml`, :func:`read_ana_json`,
  :func:`read_hidroweb`, :func:`read_hidroweb_cross_sections`
- Filtering: :func:`filter_ana_stations`
- Analysis: :func:`analyze_hydro_data`, :func:`diagnose_daily_hydrometry`,
  :func:`diagnose_station_hydrometry`
- Output: :func:`plot_hydro_data`, :func:`table_hydro_data`,
  :func:`write_hydro_data`
"""

import logging

from .analysis import analyze_hydro_data
from .auth import AnaToken, ana_authenticate
from .core import download_hidroweb_data, extract_data
from .diagnostics import diagnose_daily_hydrometry, diagnose_station_hydrometry
from .dispatch import get_ana_data, get_ana_data_batch
from .api_inventory import get_ana_stations
from .exceptions import PyHidroWebError
from .internal_data import download_ana_cross_section_vertices
from .logging_config import setup_logging
from .output import write_hydro_data
from .plotting import plot_hydro_data
from .readers import (
    read_ana_json,
    read_ana_xml,
    read_hidroweb,
    read_hidroweb_cross_sections,
)
from .stations import filter_ana_stations
from .tables import table_hydro_data

__version__ = "2.0.0"
__author__ = "pyHidroWeb Contributors"

__all__ = [
    # hydroDataBR-equivalent public API
    "ana_authenticate",
    "AnaToken",
    "get_ana_data",
    "get_ana_data_batch",
    "get_ana_stations",
    "download_ana_cross_section_vertices",
    "read_ana_xml",
    "read_ana_json",
    "read_hidroweb",
    "read_hidroweb_cross_sections",
    "filter_ana_stations",
    "analyze_hydro_data",
    "diagnose_daily_hydrometry",
    "diagnose_station_hydrometry",
    "plot_hydro_data",
    "table_hydro_data",
    "write_hydro_data",
    # legacy pyHidroWeb API (deprecated wrappers)
    "download_hidroweb_data",
    "extract_data",
    "PyHidroWebError",
    "setup_logging",
]

# Configure logging by default
logging.getLogger(__name__).addHandler(logging.NullHandler())
