"""Bundled ANA datasets (snapshot 2026-06) and the optional vertices download.

The Parquet files under ``pyhydroweb/data/`` were converted from the .rda
datasets bundled with hydrostat/hydroDataBR (MIT), themselves a static
snapshot of ANA data taken in June 2026 (see ``tools/convert_rda_to_parquet.py``).
The snapshot is useful for quick lookups, examples and offline diagnostics but
does not replace the live ANA services.

Security note: unlike the R package, the SHA-256 check on the optional
download is mandatory by default (``verify_checksum=False`` must be explicit),
and the downloaded RDS is only parsed with :mod:`pyreadr` (no arbitrary code
execution, unlike R's ``readRDS`` promise objects).
"""

from __future__ import annotations

import hashlib
import io
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from .exceptions import ChecksumMismatchError, DownloadError, MissingDependencyError

#: Snapshot label of the bundled datasets.
INTERNAL_SNAPSHOT = "2026-06"

DATA_DIR = Path(__file__).resolve().parent / "data"

DATASETS = (
    "ana_stations",
    "ana_discharge_measurements",
    "ana_rating_curves",
    "ana_rating_curve_summary",
    "ana_cross_sections",
    "ana_cross_section_summary",
)

#: Optional cross-section vertices published in the hydroDataBR repository.
OPTIONAL_DATA_BASE_URL = (
    "https://raw.githubusercontent.com/hydrostat/hydroDataBR/main/data-optional"
)
OPTIONAL_VERTICES_VERSION = "2026-06"


def load_internal(name: str) -> pd.DataFrame:
    """Load one bundled dataset by name (cached)."""
    if name not in DATASETS:
        raise ValueError(f"Unknown internal dataset {name!r}. Valid: {DATASETS}")
    return _load_parquet(name).copy()


@lru_cache(maxsize=None)
def _load_parquet(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.parquet"
    if not path.is_file():
        raise FileNotFoundError(
            f"Bundled dataset not found: {path}. Reinstall pyhydroweb or run "
            "tools/convert_rda_to_parquet.py."
        )
    return pd.read_parquet(path)


def load_ana_stations() -> pd.DataFrame:
    """Station inventory snapshot (37,584 stations, 27 columns)."""
    return load_internal("ana_stations")


def load_ana_discharge_measurements() -> pd.DataFrame:
    """Conventional discharge measurements snapshot."""
    return load_internal("ana_discharge_measurements")


def load_ana_rating_curves() -> pd.DataFrame:
    """Rating-curve segments snapshot (Q = a*(h-h0)^n)."""
    return load_internal("ana_rating_curves")


def load_ana_rating_curve_summary() -> pd.DataFrame:
    """One row per complete rating curve."""
    return load_internal("ana_rating_curve_summary")


def load_ana_cross_sections() -> pd.DataFrame:
    """Cross-section metadata snapshot (no vertices)."""
    return load_internal("ana_cross_sections")


def load_ana_cross_section_summary() -> pd.DataFrame:
    """Per-station cross-section summary."""
    return load_internal("ana_cross_section_summary")


def _default_cache_dir() -> Path:
    return Path.home() / ".cache" / "pyhydroweb"


def download_ana_cross_section_vertices(
    path: Optional[Path] = None,
    version: str = OPTIONAL_VERTICES_VERSION,
    read: bool = True,
    overwrite: bool = False,
    verify_checksum: bool = True,
    url: Optional[str] = None,
    metadata_url: Optional[str] = None,
    timeout: float = 300,
):
    """Download the full cross-section vertices dataset (~14 MB RDS).

    The dataset (2,170,742 vertices for 2,842 stations) is too large to bundle
    and is published in the hydroDataBR GitHub repository with a SHA-256 in a
    companion metadata CSV.  The checksum is verified by default; pass
    ``verify_checksum=False`` only if you accept an unverified file.

    Returns the parsed DataFrame when ``read=True`` (requires the optional
    dependency ``pyreadr``), else the local file path.
    """
    import requests

    if version != OPTIONAL_VERTICES_VERSION:
        raise ValueError(
            f"Only version {OPTIONAL_VERTICES_VERSION!r} is available; got {version!r}."
        )
    file_name = f"ana_cross_section_vertices_{version}.rds"
    data_url = url or f"{OPTIONAL_DATA_BASE_URL}/{file_name}"
    meta_url = (
        metadata_url
        or f"{OPTIONAL_DATA_BASE_URL}/ana_cross_section_vertices_{version}_metadata.csv"
    )
    cache_dir = Path(path) if path is not None else _default_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    local_file = cache_dir / file_name

    if not local_file.is_file() or overwrite:
        try:
            response = requests.get(data_url, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DownloadError(
                f"Could not download {file_name}: {exc}"
            ) from None
        local_file.write_bytes(response.content)

    if verify_checksum:
        expected = _expected_sha256(meta_url, timeout)
        actual = hashlib.sha256(local_file.read_bytes()).hexdigest()
        if actual.lower() != expected.lower():
            local_file.unlink(missing_ok=True)
            raise ChecksumMismatchError(
                "Checksum mismatch for the downloaded vertices file; the local "
                "copy was removed. Retry, or inspect the source repository."
            )

    if not read:
        return local_file
    try:
        import pyreadr
    except ImportError:
        raise MissingDependencyError(
            "Reading the vertices RDS requires the optional dependency pyreadr "
            "(pip install pyhydroweb[vertices]); pass read=False to only "
            "download the file."
        ) from None
    result = pyreadr.read_r(str(local_file))
    return next(iter(result.values()))


def _expected_sha256(metadata_url: str, timeout: float) -> str:
    import requests

    try:
        response = requests.get(metadata_url, timeout=timeout)
        response.raise_for_status()
        metadata = pd.read_csv(io.StringIO(response.text))
        value = str(metadata["sha256"].iloc[0]).strip()
        if not value:
            raise KeyError("sha256")
        return value
    except Exception as exc:  # noqa: BLE001 - single mandatory-integrity gate
        raise ChecksumMismatchError(
            "Could not obtain the published SHA-256 for the vertices file "
            f"({exc}). Refusing the unverified download; pass "
            "verify_checksum=False to override explicitly."
        ) from None
