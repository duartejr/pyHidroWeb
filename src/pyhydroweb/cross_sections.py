"""Source-neutral cross-section helpers.

Python translation of hydroDataBR's ``R/cross-sections.R`` (hydrostat/
hydroDataBR, MIT): normalize heterogeneous inputs into ``sections`` and
``vertices`` tables, summarize them, and select individual profiles.
"""

from __future__ import annotations

from typing import Dict, Optional, Union

import pandas as pd

from .contract import find_first_column

_DISTANCE_CANDIDATES = (
    "vertex_distance_m",
    "distance_m",
    "horizontal_distance_m",
    "x_distance_m",
    "x_m",
    "x",
)
_STAGE_CM_CANDIDATES = (
    "vertex_stage_cm",
    "stage_cm",
    "cota_cm",
    "elevation_cm",
    "y_cm",
    "y",
)
_STAGE_M_CANDIDATES = ("vertex_stage_m", "stage_m", "cota_m", "elevation_m", "y_m")


def extract_cross_sections(data) -> Dict[str, pd.DataFrame]:
    """Normalize a frame/dict into ``{"sections": ..., "vertices": ...}``.

    A bare DataFrame counts as vertices when it has both a distance and a
    stage column; otherwise it is treated as a sections table.
    """
    if isinstance(data, dict):
        sections = None
        vertices = None
        for key in ("sections", "section_summary", "summary", "cross_sections", "cross_section_data"):
            if isinstance(data.get(key), pd.DataFrame):
                sections = data[key]
                break
        for key in ("vertices", "cross_section_vertices", "points", "profiles"):
            if isinstance(data.get(key), pd.DataFrame):
                vertices = data[key]
                break
        if sections is None and vertices is None and isinstance(data.get("data"), (dict, pd.DataFrame)):
            return extract_cross_sections(data["data"])
        return {
            "sections": sections if sections is not None else pd.DataFrame(),
            "vertices": vertices if vertices is not None else pd.DataFrame(),
        }
    if isinstance(data, pd.DataFrame):
        has_distance = find_first_column(data, _DISTANCE_CANDIDATES) is not None
        has_stage = (
            find_first_column(data, _STAGE_CM_CANDIDATES) is not None
            or find_first_column(data, _STAGE_M_CANDIDATES) is not None
        )
        if has_distance and has_stage:
            return {"sections": pd.DataFrame(), "vertices": data}
        return {"sections": data, "vertices": pd.DataFrame()}
    raise TypeError("Could not interpret the input as cross-section data.")


def prepare_cross_section_vertices(
    cross_sections, station_code=None
) -> pd.DataFrame:
    """Standardized vertices table: station, id, date, order, distance, stage."""
    vertices = extract_cross_sections(cross_sections)["vertices"]
    if vertices.empty:
        raise ValueError("No cross-section vertices were found in the input.")
    station_col = find_first_column(vertices, ("station_code", "station", "codigo_estacao"))
    id_col = find_first_column(
        vertices, ("cross_section_id", "section_id", "profile_id", "perfil_id")
    )
    date_col = find_first_column(
        vertices,
        ("measurement_datetime", "measurement_date", "section_date", "survey_date", "date"),
    )
    order_col = find_first_column(
        vertices, ("vertex_order", "point_order", "order", "sequence", "seq")
    )
    distance_col = find_first_column(vertices, _DISTANCE_CANDIDATES)
    stage_cm_col = find_first_column(vertices, _STAGE_CM_CANDIDATES)
    stage_m_col = find_first_column(vertices, _STAGE_M_CANDIDATES)
    if distance_col is None:
        raise ValueError("The vertices table has no distance column.")
    if stage_cm_col is None and stage_m_col is None:
        raise ValueError("The vertices table has no stage column.")
    out = pd.DataFrame(
        {
            "station_code": vertices[station_col] if station_col else None,
            "cross_section_id": vertices[id_col] if id_col else None,
            "measurement_date": pd.to_datetime(
                vertices[date_col], errors="coerce"
            ).dt.date
            if date_col
            else None,
            "vertex_order": vertices[order_col] if order_col else range(1, len(vertices) + 1),
            "vertex_distance_m": pd.to_numeric(
                vertices[distance_col], errors="coerce"
            ),
            "vertex_stage_cm": pd.to_numeric(vertices[stage_cm_col], errors="coerce")
            if stage_cm_col
            else pd.to_numeric(vertices[stage_m_col], errors="coerce") * 100.0,
        }
    )
    if station_code is not None:
        out = out[out["station_code"].astype(str) == str(station_code)]
    out = out[out["vertex_distance_m"].notna() & out["vertex_stage_cm"].notna()]
    return out.sort_values(
        ["station_code", "cross_section_id", "vertex_order", "vertex_distance_m"]
    ).reset_index(drop=True)


def section_summary_from_vertices(vertices: pd.DataFrame) -> pd.DataFrame:
    """Per-section geometry summary derived from the vertices."""
    rows = []
    for (station, section_id), group in vertices.groupby(
        ["station_code", "cross_section_id"], dropna=False
    ):
        rows.append(
            {
                "station_code": station,
                "cross_section_id": section_id,
                "measurement_date": group["measurement_date"].dropna().iloc[0]
                if group["measurement_date"].notna().any()
                else None,
                "n_vertices": len(group),
                "vertex_distance_min_m": float(group["vertex_distance_m"].min()),
                "vertex_distance_max_m": float(group["vertex_distance_m"].max()),
                "vertex_stage_min_cm": float(group["vertex_stage_cm"].min()),
                "vertex_stage_max_cm": float(group["vertex_stage_cm"].max()),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["cross_section_distance_span_m"] = (
        out["vertex_distance_max_m"] - out["vertex_distance_min_m"]
    )
    out["cross_section_stage_range_cm"] = (
        out["vertex_stage_max_cm"] - out["vertex_stage_min_cm"]
    )
    return out


def cross_section_summary_by_station(sections: pd.DataFrame) -> pd.DataFrame:
    """Per-station roll-up of the sections table."""
    rows = []
    date_col = find_first_column(
        sections, ("measurement_date", "measurement_datetime")
    )
    for station, group in sections.groupby("station_code", dropna=False):
        dates = (
            pd.to_datetime(group[date_col], errors="coerce").dropna()
            if date_col
            else pd.Series(dtype="datetime64[ns]")
        )
        rows.append(
            {
                "station_code": station,
                "n_cross_sections": len(group),
                "first_cross_section_date": dates.min() if len(dates) else None,
                "last_cross_section_date": dates.max() if len(dates) else None,
            }
        )
    return pd.DataFrame(rows)


def table_cross_sections(
    cross_sections,
    station_code=None,
    level: str = "sections",
) -> pd.DataFrame:
    """Return the ``sections``, ``vertices`` or per-station ``summary`` table."""
    if level not in {"sections", "vertices", "summary"}:
        raise ValueError("level must be 'sections', 'vertices' or 'summary'.")
    extracted = extract_cross_sections(cross_sections)
    if level == "vertices":
        return prepare_cross_section_vertices(cross_sections, station_code)
    sections = extracted["sections"]
    if sections.empty and not extracted["vertices"].empty:
        sections = section_summary_from_vertices(
            prepare_cross_section_vertices(cross_sections, station_code)
        )
    elif station_code is not None and not sections.empty:
        sections = sections[
            sections["station_code"].astype(str) == str(station_code)
        ].reset_index(drop=True)
    if level == "sections":
        return sections
    return cross_section_summary_by_station(sections)


def select_cross_section_id(
    sections: pd.DataFrame,
    section_id: Optional[Union[str, int]] = None,
    section_date=None,
):
    """Pick one section id; ``"latest"``/``"first"`` select by measurement date."""
    if sections.empty:
        raise ValueError("The sections table is empty.")
    date_col = find_first_column(sections, ("measurement_date", "measurement_datetime"))
    if section_id is not None:
        token = str(section_id).lower()
        if token in {"latest", "recent", "last"} and date_col:
            ordered = sections.sort_values(date_col)
            return ordered.iloc[-1]["cross_section_id"]
        if token in {"first", "oldest"} and date_col:
            ordered = sections.sort_values(date_col)
            return ordered.iloc[0]["cross_section_id"]
        return section_id
    if section_date is not None and date_col:
        timestamps = pd.to_datetime(sections[date_col], errors="coerce")
        target = pd.Timestamp(section_date)
        nearest = (timestamps - target).abs().idxmin()
        return sections.loc[nearest, "cross_section_id"]
    return sections.iloc[0]["cross_section_id"]
