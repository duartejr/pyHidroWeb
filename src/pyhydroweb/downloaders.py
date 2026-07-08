"""Legacy bulk-download helpers, kept as thin wrappers over the new modules.

.. deprecated:: 2.0
   Use :func:`pyhydroweb.get_ana_data_batch` instead.

The GitHub raw URLs this module used before 2.0
(``anagovbr/dados-estacoes-hidro/main/dados`` and the
``Inventario_EstacoesHidrologicas_04082023.csv`` inventory) return 404 — the
upstream repository was reorganized — so the wrappers now acquire data from
the verified ANA legacy route via :func:`pyhydroweb.get_ana_data_batch` and
write one CSV per station, preserving the old on-disk behaviour.
"""

from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path
from typing import List, Optional, Sequence

from .dispatch import get_ana_data_batch
from .exceptions import DownloadError, MissingDependencyError

logger = logging.getLogger(__name__)

_DATA_TYPE_PRODUCTS = {
    "vazoes": "daily_discharge",
    "cotas": "daily_stage",
    "chuvas": "daily_rainfall",
}


def download_from_list(
    stations: Sequence,
    data_type: str = "chuvas",
    date_limits: Optional[List[str]] = None,
    path_dir: Optional[str] = None,
    **kwargs,
) -> None:
    """Download daily series for a list of stations, one CSV per station.

    .. deprecated:: 2.0
       Use :func:`pyhydroweb.get_ana_data_batch` for DataFrames instead of
       CSV files on disk.
    """
    warnings.warn(
        "download_from_list() is deprecated; use get_ana_data_batch().",
        DeprecationWarning,
        stacklevel=2,
    )
    if not stations:
        raise ValueError("stations must not be empty.")
    product = _DATA_TYPE_PRODUCTS.get(str(data_type).lower(), "daily_rainfall")
    start_date = end_date = None
    if date_limits:
        start_date = date_limits[0] or None
        if len(date_limits) > 1:
            end_date = date_limits[1] or None
    target = Path(path_dir) if path_dir else Path(os.getcwd())
    target.mkdir(parents=True, exist_ok=True)

    batch = get_ana_data_batch(
        product,
        [str(code) for code in stations],
        start_date=start_date,
        end_date=end_date,
    )
    failed = []
    for code, result in batch["results"].items():
        if result is None or result.empty:
            failed.append(code)
            continue
        result.to_csv(target / f"{code}.csv", index=False)
    if failed:
        raise DownloadError(
            f"Failed to download {len(failed)} station(s): {', '.join(failed)}."
        )


def download_from_shape(
    shape_path: str,
    data_type: str = "vazoes",
    date_limits: Optional[List[str]] = None,
    path_dir: Optional[str] = None,
    **kwargs,
) -> None:
    """Download daily series for the stations inside a shapefile boundary.

    .. deprecated:: 2.0
       Select stations with :func:`pyhydroweb.filter_ana_stations` (bounding
       box via the inventory's latitude/longitude) and use
       :func:`pyhydroweb.get_ana_data_batch`.

    Requires the optional dependency geopandas.
    """
    warnings.warn(
        "download_from_shape() is deprecated; use filter_ana_stations() + "
        "get_ana_data_batch().",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        import geopandas as gpd
    except ImportError:
        raise MissingDependencyError(
            "download_from_shape requires geopandas "
            "(pip install pyhydroweb[geo])."
        ) from None
    if not Path(shape_path).is_file():
        raise FileNotFoundError(f"Shapefile not found: {shape_path}")

    from .internal_data import load_ana_stations

    shape = gpd.read_file(shape_path)
    stations = load_ana_stations().dropna(subset=["latitude", "longitude"])
    points = gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(stations["longitude"], stations["latitude"]),
        crs=shape.crs or "EPSG:4674",
    )
    inside = gpd.sjoin(points, shape.to_crs(points.crs), predicate="within")
    if inside.empty:
        logger.warning("No inventory stations fall inside the shapefile boundary.")
        return
    download_from_list(
        inside["station_code"].astype(str).tolist(),
        data_type=data_type,
        date_limits=date_limits,
        path_dir=path_dir,
    )
