"""Export layer: ``write_hydro_data``.

Python translation of hydroDataBR's ``R/write-hydro-data.R`` (hydrostat/
hydroDataBR, MIT), adapted to Python idioms: tables export to CSV or Parquet
(instead of RDS — Parquet carries no executable payload), figures export to
PNG/PDF, and sensitive-looking columns are scrubbed before writing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Union

import pandas as pd

FORMATS = ("csv", "parquet", "png", "pdf")

_SENSITIVE_COLUMN_PATTERN = re.compile(
    r"(?i)token|authorization|cpf|cnpj|senha|password|header"
)


def _safe_table(table: pd.DataFrame) -> pd.DataFrame:
    """Drop columns whose names look credential-bearing before export."""
    keep = [
        column
        for column in table.columns
        if not _SENSITIVE_COLUMN_PATTERN.search(str(column))
    ]
    return table[keep]


def _is_figure(obj) -> bool:
    return type(obj).__module__.startswith("matplotlib")


def _resolve_format(path: Path, format: Optional[str]) -> str:
    if format is not None:
        name = str(format).lower()
        if name not in FORMATS:
            raise ValueError(f"format must be one of {FORMATS}; got {format!r}.")
        return name
    suffix = path.suffix.lower().lstrip(".")
    return suffix if suffix in FORMATS else "csv"


def write_hydro_data(
    x,
    path: Union[str, Path],
    format: Optional[str] = None,
    components: Union[str, list] = "all",
    overwrite: bool = False,
    manifest: bool = False,
) -> Dict[str, Path]:
    """Export tables and/or figures.

    ``x`` may be a single DataFrame/Figure or a dict of named components (e.g.
    the output of the diagnostics functions).  With multiple components,
    ``path`` is treated as a directory and one file per component is written
    as ``<component>.<format>``.  Existing files are only replaced with
    ``overwrite=True``.  With ``manifest=True`` a ``hydro_export_manifest.csv``
    listing every written file is added.

    Returns ``{component_name: written_path}``.
    """
    target = Path(path)
    if isinstance(x, dict):
        items = dict(x)
    else:
        items = {"data": x}
    if components != "all":
        wanted = [components] if isinstance(components, str) else list(components)
        missing = [name for name in wanted if name not in items]
        if missing:
            raise ValueError(f"Components not found: {', '.join(missing)}")
        items = {name: items[name] for name in wanted}
    items = {
        name: value
        for name, value in items.items()
        if isinstance(value, pd.DataFrame) or _is_figure(value)
    }
    if not items:
        raise ValueError("Nothing exportable was found in the input object.")

    fmt = _resolve_format(target, format)
    single_file = len(items) == 1 and target.suffix.lower().lstrip(".") in FORMATS
    if single_file:
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        target.mkdir(parents=True, exist_ok=True)

    written: Dict[str, Path] = {}
    manifest_rows = []
    for name, value in items.items():
        if _is_figure(value):
            component_format = fmt if fmt in {"png", "pdf"} else "png"
        else:
            component_format = fmt if fmt in {"csv", "parquet"} else "csv"
        destination = (
            target if single_file else target / f"{name}.{component_format}"
        )
        if destination.exists() and not overwrite:
            raise FileExistsError(
                f"{destination} already exists; pass overwrite=True to replace it."
            )
        if _is_figure(value):
            value.savefig(destination)
            shape = (None, None)
        else:
            table = _safe_table(value)
            if component_format == "parquet":
                table.to_parquet(destination, index=False)
            else:
                table.to_csv(destination, index=False, na_rep="")
            shape = table.shape
        written[name] = destination
        manifest_rows.append(
            {
                "component": name,
                "file": destination.name,
                "format": component_format,
                "rows": shape[0],
                "columns": shape[1],
                "status": "written",
            }
        )
    if manifest and not single_file:
        manifest_path = target / "hydro_export_manifest.csv"
        pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)
        written["__manifest__"] = manifest_path
    return written
