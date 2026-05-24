"""Batch download functionality for HidroWeb data."""

import logging
import os
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .exceptions import (
    DownloadError,
    MissingDependencyError,
)

logger = logging.getLogger(__name__)

# GitHub raw content URLs for HidroWeb data
AUTOMATIC_GAUGES_URL = (
    "https://raw.githubusercontent.com/anagovbr/dados-estacoes-hidro/main/dados"
)
CONVENTIONAL_GAUGES_URL = (
    "https://raw.githubusercontent.com/anagovbr/hidro-dados-estacoes-convencionais/main"
)
INVENTORY_URL = (
    "https://raw.githubusercontent.com/anagovbr/dados-estacoes-hidro/main/"
    "Inventario_EstacoesHidrologicas_04082023.csv"
)


def download_from_list(
    stations_list: List[str],
    date_limits: Optional[List[str]] = None,
    path_dir: Optional[str] = None,
    automatic_stations: bool = True,
    data_type: str = "vazoes",
    hidrologic_variable: str = "fluviometricas",
) -> None:
    """
    Download HidroWeb data for multiple stations.

    Downloads data from a list of station codes and saves to CSV files.

    Args:
        stations_list: List of station codes to download
        date_limits: Optional list [start_date, end_date] to filter data
        path_dir: Directory to save CSV files. If None, uses current directory.
        automatic_stations: If True, downloads from automatic stations;
                           if False, from conventional stations
        data_type: Data type for conventional stations ('vazoes' or 'cotas')
        hidrologic_variable: Variable type ('fluviometricas' or 'pluviometricas')

    Raises:
        DownloadError: If download fails for a station
        ValueError: If station list is empty

    Example:
        >>> download_from_list(['34879500', '34880000'])
    """
    if not stations_list:
        raise ValueError("stations_list cannot be empty")

    if path_dir is None:
        path_dir = os.getcwd()

    path_dir = Path(path_dir)
    path_dir.mkdir(parents=True, exist_ok=True)

    date_limits = date_limits or []

    logger.info(
        f"Starting download of {len(stations_list)} stations to {path_dir}"
    )

    failed_stations = []

    for station_id in stations_list:
        try:
            logger.info(f"Downloading data for station {station_id}")

            if automatic_stations:
                station_url = f"{AUTOMATIC_GAUGES_URL}/{station_id}.csv"
                dates_col = ["Data Hora"]
            else:
                station_url = (
                    f"{CONVENTIONAL_GAUGES_URL}/{hidrologic_variable}/"
                    f"{station_id}/{station_id}_{data_type}.csv"
                )
                dates_col = ["Data"]

            logger.debug(f"URL: {station_url}")

            try:
                station_data = pd.read_csv(
                    station_url,
                    delimiter=";",
                    decimal=",",
                    thousands=".",
                    na_values=[-99999, "//////", "/////"],
                    parse_dates=dates_col,
                    dayfirst=True,
                    index_col=dates_col,
                )
            except Exception as e:
                raise DownloadError(
                    f"Failed to read CSV data for station {station_id}: {e}"
                ) from e

            if date_limits and len(date_limits) == 2:
                try:
                    station_data = station_data.loc[date_limits[0] : date_limits[1]]
                    logger.debug(
                        f"Filtered data to date range {date_limits[0]}:{date_limits[1]}"
                    )
                except KeyError as e:
                    logger.warning(
                        f"No data found in specified date range for station {station_id}"
                    )

            output_file = path_dir / f"{station_id}.csv"
            station_data.to_csv(output_file)
            logger.info(f"Saved data for station {station_id} to {output_file}")

        except Exception as e:
            logger.error(f"Error downloading station {station_id}: {e}")
            failed_stations.append((station_id, str(e)))

    logger.info(f"Download completed. Processed {len(stations_list)} stations.")

    if failed_stations:
        logger.warning(
            f"Failed to download {len(failed_stations)} stations: {failed_stations}"
        )
        raise DownloadError(
            f"Failed to download {len(failed_stations)}/{len(stations_list)} stations. "
            f"Failed stations: {[s[0] for s in failed_stations]}"
        )


def download_from_shape(
    shape: str,
    date_limits: Optional[List[str]] = None,
    path_dir: Optional[str] = None,
    automatic_stations: bool = True,
    data_type: str = "vazoes",
    hidrologic_variable: str = "fluviometricas",
) -> None:
    """
    Download HidroWeb data for all stations within a geographic area.

    Reads a shapefile, finds all HidroWeb stations within its bounds,
    and downloads their data.

    Args:
        shape: Path to shapefile defining the study area
        date_limits: Optional list [start_date, end_date] to filter data
        path_dir: Directory to save CSV files. If None, uses current directory.
        automatic_stations: If True, uses automatic stations;
                           if False, uses conventional stations
        data_type: Data type for conventional stations ('vazoes' or 'cotas')
        hidrologic_variable: Variable type ('fluviometricas' or 'pluviometricas')

    Raises:
        MissingDependencyError: If geopandas is not installed
        FileNotFoundError: If shapefile not found
        DownloadError: If download fails

    Example:
        >>> download_from_shape('study_area.shp', date_limits=['2020-01-01', '2020-12-31'])
    """
    try:
        import geopandas as gpd
    except ImportError as e:
        raise MissingDependencyError(
            "geopandas is required for download_from_shape. "
            "Install it with: pip install geopandas"
        ) from e

    logger.info(f"Loading shapefile from {shape}")

    if not os.path.exists(shape):
        raise FileNotFoundError(f"Shapefile not found: {shape}")

    try:
        inventory = pd.read_csv(INVENTORY_URL, delimiter=";")
        logger.debug(f"Loaded inventory with {len(inventory)} stations")
    except Exception as e:
        raise DownloadError(f"Failed to load station inventory: {e}") from e

    if hidrologic_variable == "fluviometricas":
        inventory = inventory.query('TipoEstacao == "FLU"')
        logger.debug(
            f"Filtered to {len(inventory)} fluviometric stations"
        )

    try:
        gdf_shape = gpd.read_file(shape)
        logger.debug(f"Loaded shapefile with CRS {gdf_shape.crs}")
    except Exception as e:
        raise FileNotFoundError(f"Failed to read shapefile {shape}: {e}") from e

    try:
        gdf_inventory = gpd.GeoDataFrame(
            inventory,
            geometry=gpd.points_from_xy(inventory["Longitude"], inventory["Latitude"]),
            crs=gdf_shape.crs,
        )

        stations_in = gpd.sjoin(gdf_inventory, gdf_shape, op="within")
        stations_list = stations_in["Codigo"].astype(str).to_list()

        logger.info(
            f"Found {len(stations_list)} stations within the study area"
        )

    except Exception as e:
        raise DownloadError(
            f"Failed to identify stations within shapefile: {e}"
        ) from e

    download_from_list(
        stations_list,
        date_limits=date_limits,
        path_dir=path_dir,
        automatic_stations=automatic_stations,
        hidrologic_variable=hidrologic_variable,
        data_type=data_type,
    )
