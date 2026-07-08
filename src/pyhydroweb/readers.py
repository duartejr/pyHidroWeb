"""Local-file readers for ANA/HidroWeb data.

Python translation of hydroDataBR's ``R/read_ana_xml.R``, ``R/read_ana_json.R``,
``R/read_hidroweb.R`` and ``R/hidroweb-cross-sections.R`` (hydrostat/hydroDataBR,
MIT).  All daily readers return the standardized 8-column daily contract
(see :mod:`pyhydroweb.contract`).
"""

from __future__ import annotations

import io
import json
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

import pandas as pd

from .contract import (
    empty_daily_series,
    filter_daily_variables,
    match_daily_variables,
    require_daily_data,
    standardize_ana_daily_table,
)
from .exceptions import DataParsingError

_DAILY_ZIP_MEMBER_PATTERN = re.compile(
    r"Vazoes|Vazao|Cotas|Cota|Chuva|Chuvas|Pluv", re.IGNORECASE
)
_CROSS_SECTION_MEMBER_PATTERN = re.compile(r"PerfilTransversal\.csv$", re.IGNORECASE)
_DAILY_HEADER_PATTERN = re.compile(r"^\s*EstacaoCodigo\s*;")
_CROSS_SECTION_HEADER_PATTERN = re.compile(r"^EstacaoCodigo;")

_CROSS_SECTION_REQUIRED_COLUMNS = (
    "EstacaoCodigo",
    "NivelConsistencia",
    "Data",
    "Hora",
    "NumLevantamento",
    "TipoSecao",
    "NumVerticais",
    "Vertical",
)


def _check_local_file(path: Union[str, Path]) -> Path:
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"File not found: {resolved}")
    return resolved


# ---------------------------------------------------------------------------
# read_ana_xml
# ---------------------------------------------------------------------------

def read_ana_xml(
    path: Union[str, Path],
    variables: Union[str, Sequence[str]] = "all",
    merge_consistency: bool = True,
) -> pd.DataFrame:
    """Read a local XML file from the legacy ANA ``HidroSerieHistorica`` route.

    Each ``SerieHistorica`` element (matched by local name, regardless of
    namespace) becomes one record whose child element names are used verbatim
    as columns; the result is normalized into the daily contract.
    """
    resolved = _check_local_file(path)
    selected = match_daily_variables(variables)
    table = _read_ana_xml_series_table(resolved)
    out = standardize_ana_daily_table(
        table, source_label="ANA WebService XML", merge_consistency=merge_consistency
    )
    out = filter_daily_variables(out, selected)
    return require_daily_data(out, resolved.name)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _read_ana_xml_series_table(path: Path) -> pd.DataFrame:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise DataParsingError(f"Could not parse XML file {path.name}: {exc}") from None
    records: List[Dict[str, Optional[str]]] = []
    for element in tree.getroot().iter():
        if _local_name(element.tag) != "SerieHistorica":
            continue
        record = {}
        for child in element:
            record[_local_name(child.tag)] = child.text
        records.append(record)
    if not records:
        raise DataParsingError(
            "The XML was read but contains no SerieHistorica records. "
            "Check that the file matches the ANA HidroSerieHistorica operation."
        )
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# read_ana_json
# ---------------------------------------------------------------------------

def read_ana_json(
    path: Union[str, Path],
    variables: Union[str, Sequence[str]] = "all",
    merge_consistency: bool = True,
) -> pd.DataFrame:
    """Read a local JSON file with ANA historical-series records.

    Accepts a top-level array of records or an object with an ``items`` field.
    """
    resolved = _check_local_file(path)
    selected = match_daily_variables(variables)
    table = _read_ana_json_series_table(resolved)
    out = standardize_ana_daily_table(
        table, source_label="ANA API JSON", merge_consistency=merge_consistency
    )
    out = filter_daily_variables(out, selected)
    return require_daily_data(out, resolved.name)


def _read_ana_json_series_table(path: Path) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8") as handle:
        content = json.load(handle)
    if isinstance(content, list) and content:
        return pd.DataFrame([r for r in content if isinstance(r, dict)])
    if isinstance(content, dict):
        items = content.get("items")
        if isinstance(items, list) and items:
            return pd.DataFrame([r for r in items if isinstance(r, dict)])
    raise DataParsingError(
        "The JSON does not contain recognizable historical-series records."
    )


# ---------------------------------------------------------------------------
# read_hidroweb
# ---------------------------------------------------------------------------

def read_hidroweb(
    path: Union[str, Path],
    variables: Union[str, Sequence[str]] = "all",
    merge_consistency: bool = True,
) -> pd.DataFrame:
    """Read a local HidroWeb export (ZIP with daily CSVs, or a single CSV).

    HidroWeb CSVs are Latin-1 encoded, ``;``-separated with comma decimals and
    carry preamble lines before the ``EstacaoCodigo;...`` header.
    """
    resolved = _check_local_file(path)
    selected = match_daily_variables(variables)
    if resolved.suffix.lower() == ".zip":
        out = _read_hidroweb_zip(resolved, merge_consistency)
    else:
        table = _read_hidroweb_csv_table(resolved.read_bytes(), resolved.name)
        out = standardize_ana_daily_table(
            table,
            source_label=f"HidroWeb CSV: {resolved.name}",
            merge_consistency=merge_consistency,
        )
    out = filter_daily_variables(out, selected)
    return require_daily_data(out, resolved.name)


def _read_hidroweb_zip(path: Path, merge_consistency: bool) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        members = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".csv") and _DAILY_ZIP_MEMBER_PATTERN.search(name)
        ]
        if not members:
            raise DataParsingError(
                "The ZIP does not contain recognizable daily discharge, stage "
                "or rainfall CSV files."
            )
        frames = []
        for member in members:
            raw = archive.read(member)
            table = _read_hidroweb_csv_table(raw, member)
            frames.append(
                standardize_ana_daily_table(
                    table,
                    source_label=f"HidroWeb ZIP: {Path(member).name}",
                    merge_consistency=merge_consistency,
                )
            )
    out = pd.concat(frames, ignore_index=True) if frames else empty_daily_series()
    if not out.empty:
        out = out.sort_values(
            ["station_code", "date", "variable"], kind="stable"
        ).reset_index(drop=True)
    return out


def _read_hidroweb_csv_table(raw: bytes, name: str) -> pd.DataFrame:
    text = raw.decode("latin-1")
    lines = text.splitlines()
    header_index = None
    for index, line in enumerate(lines):
        if _DAILY_HEADER_PATTERN.match(line):
            header_index = index
            break
    if header_index is None:
        raise DataParsingError(
            f"Could not locate the EstacaoCodigo header in CSV file {name}."
        )
    csv_text = "\n".join(lines[header_index:])
    return pd.read_csv(
        io.StringIO(csv_text),
        sep=";",
        dtype=str,
        keep_default_na=False,
    )


# ---------------------------------------------------------------------------
# read_hidroweb_cross_sections
# ---------------------------------------------------------------------------

def read_hidroweb_cross_sections(
    file: Union[str, Path]
) -> Dict[str, pd.DataFrame]:
    """Read a HidroWeb ``PerfilTransversal.csv`` (bare or inside a ZIP).

    Returns ``{"sections": DataFrame, "vertices": DataFrame}`` with one row per
    cross section and one row per profile vertex, respectively.
    """
    resolved = _check_local_file(file)
    if resolved.suffix.lower() == ".zip":
        with zipfile.ZipFile(resolved) as archive:
            members = [
                name
                for name in archive.namelist()
                if _CROSS_SECTION_MEMBER_PATTERN.search(name)
            ]
            if not members:
                raise DataParsingError(
                    "No PerfilTransversal.csv file was found in the ZIP archive."
                )
            raw = archive.read(members[0])
    else:
        raw = resolved.read_bytes()
    return _parse_hidroweb_cross_sections_csv(raw)


def _parse_hidroweb_cross_sections_csv(raw: bytes) -> Dict[str, pd.DataFrame]:
    lines = raw.decode("latin-1").splitlines()
    header_index = None
    for index, line in enumerate(lines):
        if _CROSS_SECTION_HEADER_PATTERN.match(line):
            header_index = index
            break
    if header_index is None:
        raise DataParsingError(
            "The file does not contain a PerfilTransversal.csv header."
        )
    csv_text = "\n".join(lines[header_index:])
    table = pd.read_csv(
        io.StringIO(csv_text),
        sep=";",
        dtype=str,
        keep_default_na=False,
    )
    return _standardize_cross_sections_table(table)


def empty_cross_sections() -> Dict[str, pd.DataFrame]:
    """Empty ``sections``/``vertices`` frames with the standard columns."""
    sections = pd.DataFrame(
        columns=[
            "cross_section_id",
            "station_code",
            "measurement_datetime",
            "consistency_level",
            "survey_number",
            "section_type",
            "n_vertices",
            "source_status",
            "source",
        ]
    )
    vertices = pd.DataFrame(
        columns=[
            "cross_section_id",
            "cross_section_vertex_id",
            "station_code",
            "measurement_datetime",
            "consistency_level",
            "survey_number",
            "section_type",
            "vertex_order",
            "vertex_distance_m",
            "vertex_stage_cm",
            "source_status",
            "source",
        ]
    )
    return {"sections": sections, "vertices": vertices}


def _cross_section_integer(value) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"NA", "null"}:
        return None
    text = text.replace(",", ".")
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_cross_section_datetime(date_value, time_value) -> Optional[datetime]:
    try:
        date_part = datetime.strptime(str(date_value).strip(), "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None
    time_text = str(time_value or "")
    match = re.search(r"(\d{1,2}:\d{2})(?::\d{2})?", time_text)
    time_part = match.group(1) if match else "00:00"
    hours, minutes = (int(piece) for piece in time_part.split(":"))
    return datetime(
        date_part.year, date_part.month, date_part.day, hours, minutes,
        tzinfo=timezone.utc,
    )


def _parse_vertical_cell(vertical_text) -> List[Dict[str, Optional[float]]]:
    """Unpack the ``Vertical`` cell: ``|``-separated tokens of ``distance,stage``.

    The last comma-piece of each token is the stage (cm); the preceding pieces
    form the distance (m) — when the distance itself carried a decimal comma
    the extra pieces are re-joined as its fractional part.
    """
    if vertical_text is None:
        return []
    text = str(vertical_text).strip()
    if not text or text in {"NA", "null"}:
        return []
    vertices = []
    for token in text.split("|"):
        token = token.strip()
        if not token:
            continue
        pieces = [piece.strip() for piece in token.split(",")]
        if len(pieces) < 2:
            continue
        stage_text = pieces[-1]
        distance_pieces = pieces[:-1]
        if len(distance_pieces) == 1:
            distance_text = distance_pieces[0]
        else:
            distance_text = distance_pieces[0] + "." + "".join(distance_pieces[1:])
        try:
            distance = float(distance_text)
        except ValueError:
            distance = None
        try:
            stage = float(stage_text)
        except ValueError:
            stage = None
        vertices.append({"vertex_distance_m": distance, "vertex_stage_cm": stage})
    return vertices


def _standardize_cross_sections_table(raw: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if raw is None or raw.empty:
        return empty_cross_sections()
    missing = [col for col in _CROSS_SECTION_REQUIRED_COLUMNS if col not in raw.columns]
    if missing:
        raise DataParsingError(
            "PerfilTransversal.csv is missing required columns: "
            + ", ".join(missing)
        )
    source = "HidroWeb ZIP: PerfilTransversal.csv"
    section_rows = []
    vertex_rows = []
    for _, row in raw.iterrows():
        station_code = str(row["EstacaoCodigo"]).strip()
        consistency_level = _cross_section_integer(row["NivelConsistencia"])
        survey_number = _cross_section_integer(row["NumLevantamento"])
        section_type = _cross_section_integer(row["TipoSecao"])
        measurement_datetime = _parse_cross_section_datetime(row["Data"], row["Hora"])
        vertices = _parse_vertical_cell(row["Vertical"])
        datetime_text = (
            measurement_datetime.strftime("%Y%m%d%H%M%S")
            if measurement_datetime is not None
            else "NA"
        )
        cross_section_id = "_".join(
            [
                station_code,
                datetime_text,
                "NA" if survey_number is None else str(survey_number),
                "NA" if section_type is None else str(section_type),
            ]
        )
        section_rows.append(
            {
                "cross_section_id": cross_section_id,
                "station_code": station_code,
                "measurement_datetime": measurement_datetime,
                "consistency_level": consistency_level,
                "survey_number": survey_number,
                "section_type": section_type,
                "n_vertices": len(vertices),
                "source_status": None,
                "source": source,
            }
        )
        for order, vertex in enumerate(vertices, start=1):
            vertex_rows.append(
                {
                    "cross_section_id": cross_section_id,
                    "cross_section_vertex_id": f"{cross_section_id}_{order}",
                    "station_code": station_code,
                    "measurement_datetime": measurement_datetime,
                    "consistency_level": consistency_level,
                    "survey_number": survey_number,
                    "section_type": section_type,
                    "vertex_order": order,
                    "vertex_distance_m": vertex["vertex_distance_m"],
                    "vertex_stage_cm": vertex["vertex_stage_cm"],
                    "source_status": None,
                    "source": source,
                }
            )
    empty = empty_cross_sections()
    sections = (
        pd.DataFrame(section_rows) if section_rows else empty["sections"]
    )
    vertices = pd.DataFrame(vertex_rows) if vertex_rows else empty["vertices"]
    return {"sections": sections, "vertices": vertices}
