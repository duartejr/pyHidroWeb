"""One-shot conversion of hydroDataBR's bundled .rda datasets to Parquet.

Provenance: the .rda files come from hydrostat/hydroDataBR (MIT license),
``data/`` directory — a static snapshot of ANA data taken in June 2026 and
originally derived from the HydroStat Data Explorer.  Parquet is used on the
Python side because it is columnar, compressed and — unlike RDS/pickle —
carries no executable payload.

Usage:
    python tools/convert_rda_to_parquet.py <hydroDataBR-repo-dir> <output-dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyreadr

DATASETS = (
    "ana_stations",
    "ana_discharge_measurements",
    "ana_rating_curves",
    "ana_rating_curve_summary",
    "ana_cross_sections",
    "ana_cross_section_summary",
)


def convert(repo_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in DATASETS:
        source = repo_dir / "data" / f"{name}.rda"
        result = pyreadr.read_r(str(source))
        if name not in result:
            raise SystemExit(f"{source} does not contain an object named {name}")
        frame: pd.DataFrame = result[name]
        target = output_dir / f"{name}.parquet"
        frame.to_parquet(target, index=False, compression="zstd")
        print(f"{name}: {frame.shape[0]} rows x {frame.shape[1]} cols -> {target}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    convert(Path(sys.argv[1]), Path(sys.argv[2]))
