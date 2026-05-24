"""Station metadata access and management for pyHidroWeb."""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import json

import pandas as pd

from .exceptions import MissingDependencyError, DownloadError

logger = logging.getLogger(__name__)

# Official SNIRH inventory URL
SNIRH_INVENTORY_URL = (
    "https://www.snirh.gov.br/hidroweb/download/inventario.zip"
)

# Cache location for station metadata
METADATA_CACHE_DIR = Path.home() / ".pyhydroweb" / "metadata"


def download_station_inventory() -> pd.DataFrame:
    """
    Download the latest station inventory from SNIRH.

    Downloads the official inventário.zip file containing all station metadata
    including coordinates, elevation, and other details.

    Returns:
        DataFrame with station metadata columns:
        - Codigo: Station code
        - Nome: Station name
        - Latitude: Station latitude
        - Longitude: Station longitude
        - Altitude: Station elevation
        - TipoEstacao: Station type (FLU=fluviometric, PLU=pluviometric)
        - ResponsavelTecnico: Technical responsible
        - ResponsavelOperacional: Operational responsible
        - Situacao: Operational status

    Raises:
        DownloadError: If download fails
        MissingDependencyError: If required library is missing
    """
    import io
    import zipfile
    import requests

    logger.info("Downloading station inventory from SNIRH...")

    try:
        response = requests.get(SNIRH_INVENTORY_URL, timeout=60)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise DownloadError(f"Failed to download SNIRH inventory: {e}") from e

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            # Find the CSV file in the zip
            csv_files = [f for f in zip_file.namelist() if f.endswith(".csv")]

            if not csv_files:
                raise DownloadError(
                    "No CSV file found in SNIRH inventory zip"
                )

            # Read the first CSV file found
            with zip_file.open(csv_files[0]) as csv_file:
                df = pd.read_csv(
                    csv_file,
                    delimiter=";",
                    encoding="utf-8",
                    dtype={"Codigo": str},
                )
                logger.info(
                    f"Successfully loaded {len(df)} stations from inventory"
                )
                return df

    except zipfile.BadZipFile as e:
        raise DownloadError(f"Invalid zip file from SNIRH: {e}") from e
    except Exception as e:
        raise DownloadError(f"Failed to parse SNIRH inventory: {e}") from e


def get_cached_inventory(
    max_age_days: int = 30, force_refresh: bool = False
) -> pd.DataFrame:
    """
    Get station inventory with caching.

    Downloads inventory if not cached or if cache is older than max_age_days.

    Args:
        max_age_days: Maximum age of cache in days (default: 30)
        force_refresh: Force download even if cache exists

    Returns:
        DataFrame with station metadata

    Raises:
        DownloadError: If download fails
    """
    import time
    from datetime import datetime, timedelta

    METADATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = METADATA_CACHE_DIR / "stations.csv"

    # Check if cache exists and is fresh
    if cache_file.exists() and not force_refresh:
        cache_age = time.time() - cache_file.stat().st_mtime
        cache_age_days = cache_age / (24 * 3600)

        if cache_age_days < max_age_days:
            logger.debug(
                f"Using cached inventory ({cache_age_days:.1f} days old)"
            )
            return pd.read_csv(cache_file, dtype={"Codigo": str})

    # Download fresh copy
    df = download_station_inventory()

    # Cache it
    df.to_csv(cache_file, index=False, encoding="utf-8")
    logger.debug(f"Cached inventory to {cache_file}")

    return df


def get_station_metadata(station_code: str) -> Optional[Dict]:
    """
    Get metadata for a specific station.

    Args:
        station_code: Station code to lookup

    Returns:
        Dictionary with station metadata or None if not found

    Example:
        >>> metadata = get_station_metadata("34879500")
        >>> print(metadata['Nome'], metadata['Latitude'], metadata['Longitude'])
    """
    inventory = get_cached_inventory()

    station_data = inventory[inventory["Codigo"].astype(str) == str(station_code)]

    if station_data.empty:
        logger.warning(f"Station {station_code} not found in inventory")
        return None

    return station_data.iloc[0].to_dict()


def get_stations_in_bounds(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    station_type: Optional[str] = None,
) -> pd.DataFrame:
    """
    Get all stations within geographic bounds.

    Args:
        min_lat: Minimum latitude
        max_lat: Maximum latitude
        min_lon: Minimum longitude
        max_lon: Maximum longitude
        station_type: Filter by station type ('FLU' or 'PLU'), or None for all

    Returns:
        DataFrame with stations in bounds

    Example:
        >>> stations = get_stations_in_bounds(-16, -15, -46, -45)
        >>> print(f"Found {len(stations)} stations in bounds")
    """
    inventory = get_cached_inventory()

    # Filter by bounds
    filtered = inventory[
        (inventory["Latitude"] >= min_lat)
        & (inventory["Latitude"] <= max_lat)
        & (inventory["Longitude"] >= min_lon)
        & (inventory["Longitude"] <= max_lon)
    ]

    # Filter by station type if specified
    if station_type:
        filtered = filtered[filtered["TipoEstacao"] == station_type.upper()]

    logger.info(f"Found {len(filtered)} stations in bounds")
    return filtered


def get_stations_in_polygon(
    polygon_coords: List[Tuple[float, float]],
    station_type: Optional[str] = None,
) -> pd.DataFrame:
    """
    Get all stations within a polygon area.

    Uses geopandas for spatial operations. Polygon coordinates should be
    in (latitude, longitude) format.

    Args:
        polygon_coords: List of (lat, lon) tuples defining polygon vertices
        station_type: Filter by station type ('FLU' or 'PLU'), or None for all

    Returns:
        DataFrame with stations within polygon

    Raises:
        MissingDependencyError: If geopandas not installed

    Example:
        >>> polygon = [(-16, -46), (-16, -45), (-15, -45), (-15, -46)]
        >>> stations = get_stations_in_polygon(polygon, station_type='FLU')
    """
    try:
        from shapely.geometry import Polygon
        import geopandas as gpd
    except ImportError as e:
        raise MissingDependencyError(
            "geopandas and shapely are required for polygon selection. "
            "Install with: pip install geopandas shapely"
        ) from e

    inventory = get_cached_inventory()

    # Create polygon (note: shapely expects (lon, lat) not (lat, lon))
    polygon = Polygon([(lon, lat) for lat, lon in polygon_coords])

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(
        inventory,
        geometry=gpd.points_from_xy(inventory["Longitude"], inventory["Latitude"]),
    )

    # Filter by polygon
    filtered = gdf[gdf.geometry.within(polygon)]

    # Filter by station type if specified
    if station_type:
        filtered = filtered[filtered["TipoEstacao"] == station_type.upper()]

    logger.info(f"Found {len(filtered)} stations within polygon")
    return filtered[[col for col in filtered.columns if col != "geometry"]]


def get_all_stations(station_type: Optional[str] = None) -> pd.DataFrame:
    """
    Get all available stations.

    Args:
        station_type: Filter by station type ('FLU' or 'PLU'), or None for all

    Returns:
        DataFrame with all stations

    Example:
        >>> fluviometric = get_all_stations(station_type='FLU')
        >>> print(f"Total fluviometric stations: {len(fluviometric)}")
    """
    inventory = get_cached_inventory()

    if station_type:
        inventory = inventory[
            inventory["TipoEstacao"] == station_type.upper()
        ]

    logger.info(f"Retrieved {len(inventory)} stations")
    return inventory


def get_nearby_stations(
    latitude: float,
    longitude: float,
    radius_km: float = 50,
    station_type: Optional[str] = None,
) -> pd.DataFrame:
    """
    Get stations near a geographic point.

    Args:
        latitude: Reference latitude
        longitude: Reference longitude
        radius_km: Search radius in kilometers (default: 50)
        station_type: Filter by station type ('FLU' or 'PLU')

    Returns:
        DataFrame with nearby stations, sorted by distance

    Example:
        >>> nearby = get_nearby_stations(-15.5, -45.5, radius_km=100)
    """
    from math import radians, cos, sin, asin, sqrt

    inventory = get_cached_inventory()

    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates in km."""
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        km = 6371 * c
        return km

    # Calculate distance for each station
    inventory["distance_km"] = inventory.apply(
        lambda row: haversine(
            latitude, longitude, row["Latitude"], row["Longitude"]
        ),
        axis=1,
    )

    # Filter by radius
    filtered = inventory[inventory["distance_km"] <= radius_km]

    # Filter by station type if specified
    if station_type:
        filtered = filtered[filtered["TipoEstacao"] == station_type.upper()]

    # Sort by distance
    filtered = filtered.sort_values("distance_km")

    logger.info(f"Found {len(filtered)} stations within {radius_km} km")
    return filtered


def clear_metadata_cache() -> None:
    """Clear the cached metadata files."""
    import shutil

    if METADATA_CACHE_DIR.exists():
        shutil.rmtree(METADATA_CACHE_DIR)
        logger.info("Cleared metadata cache")
