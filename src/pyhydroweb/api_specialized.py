"""Specialized hydrometric products from the ANA HidroWebService.

Python translation of hydroDataBR's ``R/ana-specialized.R`` (hydrostat/
hydroDataBR, MIT): discharge measurement summaries, rating curves and
cross-section profiles.  These routes require authentication and reject
windows longer than 366 days — long ranges are split automatically by the
dispatcher (see :mod:`pyhydroweb.dispatch`).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Sequence, Union

import pandas as pd

from .auth import AnaToken, ana_authenticate, request_json
from .api_inventory import extract_items, record_value
from .contract import (
    is_missing_token,
    normalize_station_code,
    parse_ana_date,
    parse_ana_numeric,
)
from .windowing import assert_api_window

DISCHARGE_MEASUREMENTS_ENDPOINT = "/HidroSerieResumoDescarga/v1"
RATING_CURVES_ENDPOINT = "/HidroSerieCurvaDescarga/v1"
CROSS_SECTIONS_ENDPOINT = "/HidroSeriePerfilTransversal/v1"

STATION_PARAM = "Código da Estação"
START_PARAM = "Data Inicial (yyyy-MM-dd)"
END_PARAM = "Data Final (yyyy-MM-dd)"
TYPE_FILTER_PARAM = "Tipo Filtro Data"
TYPE_FILTER_VALUE = "DATA_LEITURA"

_CHILD_ARRAY_KEYS = (
    "medicoes",
    "Medicoes",
    "resumoDescarga",
    "ResumoDescarga",
    "serieResumoDescarga",
    "SerieResumoDescarga",
    "segmentos",
    "Segmentos",
    "trechos",
    "Trechos",
    "curvas",
    "Curvas",
    "curvaDescarga",
    "CurvaDescarga",
    "serieCurvaDescarga",
    "SerieCurvaDescarga",
    "vertices",
    "Vertices",
    "pontos",
    "Pontos",
    "perfil",
    "Perfil",
    "perfilTransversal",
    "PerfilTransversal",
    "pontosPerfilTransversal",
    "PontosPerfilTransversal",
)

_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
)


def parse_api_datetime(value) -> Optional[datetime]:
    """Parse an API datetime string (UTC when no offset is present)."""
    if value is None or is_missing_token(value):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = re.sub(r"\.\d+", "", str(value).strip())
    for fmt in _DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def flatten_records(response) -> List[Dict]:
    """Extract records, merging parent scalars into nested child arrays.

    ANA responses sometimes nest per-measurement records under keys such as
    ``medicoes`` or ``segmentos`` while station-level fields live on the parent
    object (mirrors ``ana_stage04_merge_parent_child``).
    """
    records = []
    for item in extract_items(response):
        child_lists = [
            item[key]
            for key in _CHILD_ARRAY_KEYS
            if isinstance(item.get(key), list) and item[key]
        ]
        if not child_lists:
            records.append(item)
            continue
        parent_scalars = {
            key: value
            for key, value in item.items()
            if not isinstance(value, (list, dict))
        }
        for child_list in child_lists:
            for child in child_list:
                if isinstance(child, dict):
                    records.append({**parent_scalars, **child})
    return records


def _resolve_token(token: Optional[AnaToken], timeout: float) -> AnaToken:
    if token is not None:
        return token
    return ana_authenticate(timeout=timeout)


def _format_query_date(value: Union[str, date, None]) -> Optional[str]:
    if value is None:
        return None
    parsed = parse_ana_date(value)
    if parsed is None:
        raise ValueError(f"Could not interpret date: {value!r}")
    return parsed.strftime("%Y-%m-%d")


def _product_query(
    station_code,
    start_date=None,
    end_date=None,
    consistency_level=None,
    date_filter: bool = False,
) -> Dict[str, str]:
    query = {STATION_PARAM: str(station_code)}
    if date_filter and (start_date is not None or end_date is not None):
        query[TYPE_FILTER_PARAM] = TYPE_FILTER_VALUE
    start_text = _format_query_date(start_date)
    end_text = _format_query_date(end_date)
    if start_text:
        query[START_PARAM] = start_text
    if end_text:
        query[END_PARAM] = end_text
    if consistency_level is not None:
        query["Nível de Consistência"] = str(consistency_level)
    return query


# ---------------------------------------------------------------------------
# Discharge measurements
# ---------------------------------------------------------------------------

_MEASUREMENT_FIELDS = {
    "station_code": (
        ("CodigoEstacao", "Codigo_Estacao", "CodEstacao"),
        normalize_station_code,
    ),
    "measurement_datetime": (
        (
            "Data_Hora_Dado",
            "DataHoraDado",
            "Data_Hora_Medicao",
            "DataHoraMedicao",
            "DataMedicao",
            "Data_Medicao",
            "Data",
        ),
        parse_api_datetime,
    ),
    "consistency_level": (
        ("Nivel_Consistencia", "NivelConsistencia", "Consistencia"),
        lambda v: None if is_missing_token(v) else str(v).strip(),
    ),
    "stage_cm": (
        ("Cota", "Cota (cm)", "Cota_cm", "CotaMedida", "Nivel"),
        parse_ana_numeric,
    ),
    "discharge_m3s": (
        (
            "Vazao",
            "Vazão",
            "Vazao (m3/s)",
            "Vazão (m3/s)",
            "Vazao_m3s",
            "Vazao_m3_s",
            "VazaoMedida",
            "DescargaLiquida",
        ),
        parse_ana_numeric,
    ),
    "wetted_area_m2": (
        (
            "Area_Molhada",
            "AreaMolhada",
            "Area Molhada",
            "Area_Molhada (m2)",
            "AreaSecao",
            "AreaDaSecao",
        ),
        parse_ana_numeric,
    ),
    "width_m": (("Largura", "Largura (m)", "Largura_m"), parse_ana_numeric),
    "mean_depth_m": (
        ("Profundidade", "Profundidade (m)", "ProfundidadeMedia", "ProfMedia"),
        parse_ana_numeric,
    ),
    "mean_velocity_ms": (
        ("Vel_Media", "VelMedia", "Vel_Media (m/s)", "VelocidadeMedia"),
        parse_ana_numeric,
    ),
}

MEASUREMENT_COLUMNS = list(_MEASUREMENT_FIELDS) + ["source"]


def standardize_discharge_measurements(response) -> pd.DataFrame:
    """Normalize a discharge-measurement response to the standard columns."""
    rows = []
    for record in flatten_records(response):
        row = {
            column: parser(record_value(record, candidates))
            for column, (candidates, parser) in _MEASUREMENT_FIELDS.items()
        }
        row["source"] = "ana_hidrowebservice_discharge_measurements"
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=MEASUREMENT_COLUMNS)
    out = pd.DataFrame(rows, columns=MEASUREMENT_COLUMNS)
    return out[out["station_code"].notna() | out["measurement_datetime"].notna()].reset_index(
        drop=True
    )


def get_ana_discharge_measurements(
    station_code,
    start_date=None,
    end_date=None,
    consistency_level=None,
    token: Optional[AnaToken] = None,
    timeout: float = 120,
) -> pd.DataFrame:
    """Discharge measurement summaries for one station (window <= 366 days)."""
    if start_date is not None and end_date is not None:
        assert_api_window(start_date, end_date)
    token = _resolve_token(token, timeout)
    response = request_json(
        DISCHARGE_MEASUREMENTS_ENDPOINT,
        query=_product_query(
            station_code, start_date, end_date, consistency_level, date_filter=True
        ),
        token=token,
        timeout=timeout,
    )
    return standardize_discharge_measurements(response)


# ---------------------------------------------------------------------------
# Rating curves
# ---------------------------------------------------------------------------

_RATING_FIELDS = {
    "station_code": (
        ("CodigoEstacao", "Codigo_Estacao", "CodEstacao"),
        normalize_station_code,
    ),
    "valid_from": (
        ("DataInicio", "Data_Inicio", "InicioValidade", "DataValidadeInicial"),
        parse_ana_date,
    ),
    "valid_to": (
        ("DataFim", "Data_Fim", "FimValidade", "DataValidadeFinal"),
        parse_ana_date,
    ),
    "consistency_level": (
        ("NivelConsistencia", "Nivel_Consistencia"),
        lambda v: None if is_missing_token(v) else str(v).strip(),
    ),
    "segment_number": (
        ("NumeroTrecho", "Numero_Trecho", "Trecho", "Segmento"),
        lambda v: None if parse_ana_numeric(v) is None else int(parse_ana_numeric(v)),
    ),
    "n_segments_reported": (
        ("NumeroTotalTrechos", "Numero_Trechos", "TotalTrechos"),
        lambda v: None if parse_ana_numeric(v) is None else int(parse_ana_numeric(v)),
    ),
    "curve_type": (
        ("TipoCurva",),
        lambda v: None if is_missing_token(v) else str(v).strip(),
    ),
    "equation_type": (
        ("TipoEquacao", "Equacao"),
        lambda v: None if is_missing_token(v) else str(v).strip(),
    ),
    "stage_min_cm": (("CotaMinima", "CotaInicial"), parse_ana_numeric),
    "stage_max_cm": (("CotaMaxima", "CotaFinal"), parse_ana_numeric),
    "table_stage_step_cm": (("IntervaloCota", "PassoCota"), parse_ana_numeric),
    "coefficient_a": (("CoeficienteA", "CoefA", "A"), parse_ana_numeric),
    "coefficient_h0_cm": (("CoeficienteH0", "CoefH0", "H0"), parse_ana_numeric),
    "coefficient_n": (("CoeficienteN", "CoefN", "N"), parse_ana_numeric),
    "rating_curve_id": (
        ("CodigoCurva", "IdCurva", "IdentificadorCurva"),
        lambda v: None if is_missing_token(v) else str(v).strip(),
    ),
    "rating_curve_segment_id": (
        ("CodigoTrecho", "IdTrecho"),
        lambda v: None if is_missing_token(v) else str(v).strip(),
    ),
}

RATING_CURVE_COLUMNS = [
    "rating_curve_id",
    "rating_curve_segment_id",
    "station_code",
    "valid_from",
    "valid_to",
    "consistency_level",
    "segment_number",
    "n_segments_reported",
    "curve_type",
    "equation_type",
    "stage_min_cm",
    "stage_max_cm",
    "table_stage_step_cm",
    "coefficient_a",
    "coefficient_h0_cm",
    "coefficient_h0_m",
    "coefficient_n",
    "source",
]


def standardize_rating_curves(response) -> pd.DataFrame:
    """Normalize a rating-curve response; synthesizes missing curve/segment ids."""
    rows = []
    for record in flatten_records(response):
        row = {
            column: parser(record_value(record, candidates))
            for column, (candidates, parser) in _RATING_FIELDS.items()
        }
        row["source"] = "ana_hidrowebservice_rating_curves"
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=RATING_CURVE_COLUMNS)
    out = pd.DataFrame(rows)
    out["coefficient_h0_m"] = out["coefficient_h0_cm"].map(
        lambda v: None if v is None or pd.isna(v) else v / 100.0
    )

    def synthesize_curve_id(row):
        if row["rating_curve_id"]:
            return row["rating_curve_id"]
        return "_".join(
            str(part)
            for part in (row["station_code"], row["valid_from"], row["valid_to"])
        )

    out["rating_curve_id"] = out.apply(synthesize_curve_id, axis=1)
    out["rating_curve_segment_id"] = out.apply(
        lambda row: row["rating_curve_segment_id"]
        or f"{row['rating_curve_id']}_{row['segment_number']}",
        axis=1,
    )
    return out[RATING_CURVE_COLUMNS].reset_index(drop=True)


def get_ana_rating_curves(
    station_code,
    start_date=None,
    end_date=None,
    consistency_level=None,
    token: Optional[AnaToken] = None,
    timeout: float = 120,
) -> pd.DataFrame:
    """Rating curves for one station (window <= 366 days when dates given)."""
    if start_date is not None and end_date is not None:
        assert_api_window(start_date, end_date)
    token = _resolve_token(token, timeout)
    response = request_json(
        RATING_CURVES_ENDPOINT,
        query=_product_query(station_code, start_date, end_date, consistency_level),
        token=token,
        timeout=timeout,
    )
    return standardize_rating_curves(response)


# ---------------------------------------------------------------------------
# Cross sections
# ---------------------------------------------------------------------------

_SECTION_SCALAR_FIELDS = {
    "station_code": (
        ("CodigoEstacao", "EstacaoCodigo"),
        normalize_station_code,
    ),
    "measurement_datetime": (
        ("Data_Hora_Medicao", "DataHoraMedicao", "Data"),
        parse_api_datetime,
    ),
    "consistency_level": (
        ("Nivel_Consistencia", "NivelConsistencia"),
        lambda v: None if parse_ana_numeric(v) is None else int(parse_ana_numeric(v)),
    ),
    "survey_number": (
        ("Num_Levantamento", "NumLevantamento", "NumeroLevantamento"),
        lambda v: None if parse_ana_numeric(v) is None else int(parse_ana_numeric(v)),
    ),
    "section_type": (
        ("Tipo_Secao", "TipoSecao", "TipoSecaoTransversal"),
        lambda v: None if parse_ana_numeric(v) is None else int(parse_ana_numeric(v)),
    ),
    "source_record_id": (
        ("Registro_ID", "CodigoPerfil", "Codigo_Perfil", "IdPerfil"),
        lambda v: None if is_missing_token(v) else str(v).strip(),
    ),
    "n_vertices_reported": (
        ("Num_Verticais", "NumVerticais"),
        lambda v: None if parse_ana_numeric(v) is None else int(parse_ana_numeric(v)),
    ),
}

_VERTEX_CHILD_KEYS = (
    "vertices",
    "Vertices",
    "pontos",
    "Pontos",
    "perfil",
    "Perfil",
    "perfilTransversal",
    "PerfilTransversal",
    "pontosPerfilTransversal",
    "PontosPerfilTransversal",
)

CROSS_SECTIONS_SOURCE = "ana_hidrowebservice_cross_sections"


def empty_api_cross_sections() -> Dict[str, pd.DataFrame]:
    """Empty standardized ``sections``/``vertices`` frames for the API route."""
    sections = pd.DataFrame(
        columns=[
            "cross_section_id",
            "station_code",
            "measurement_datetime",
            "consistency_level",
            "survey_number",
            "section_type",
            "source_record_id",
            "n_vertices",
            "n_vertices_reported",
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
            "source",
        ]
    )
    return {"sections": sections, "vertices": vertices}


def _parse_vertex_records(item: Dict) -> List[Dict[str, Optional[float]]]:
    """Extract vertex records from child arrays or a packed ``Vertical`` cell."""
    for key in _VERTEX_CHILD_KEYS:
        child = item.get(key)
        if isinstance(child, list) and child:
            vertices = []
            for point in child:
                if not isinstance(point, dict):
                    continue
                vertices.append(
                    {
                        "vertex_distance_m": parse_ana_numeric(
                            record_value(point, ("Distancia", "Distancia_m", "X"))
                        ),
                        "vertex_stage_cm": parse_ana_numeric(
                            record_value(point, ("Cota", "Cota_cm", "Y"))
                        ),
                    }
                )
            return vertices
    packed = record_value(item, ("Vertical",))
    if packed is None:
        return []
    from .readers import _parse_vertical_cell

    return _parse_vertical_cell(packed)


def standardize_cross_sections(response) -> Dict[str, pd.DataFrame]:
    """Normalize a cross-section response into ``sections`` and ``vertices``."""
    items = extract_items(response)
    if not items:
        return empty_api_cross_sections()
    section_rows = []
    vertex_rows = []
    for item in items:
        scalars = {
            column: parser(record_value(item, candidates))
            for column, (candidates, parser) in _SECTION_SCALAR_FIELDS.items()
        }
        vertices = _parse_vertex_records(item)
        datetime_value = scalars["measurement_datetime"]
        datetime_text = (
            datetime_value.strftime("%Y%m%d%H%M%S")
            if datetime_value is not None
            else "NA"
        )
        cross_section_id = "_".join(
            [
                str(scalars["station_code"]),
                datetime_text,
                "NA" if scalars["survey_number"] is None else str(scalars["survey_number"]),
                "NA" if scalars["section_type"] is None else str(scalars["section_type"]),
            ]
        )
        section_rows.append(
            {
                "cross_section_id": cross_section_id,
                **{k: scalars[k] for k in (
                    "station_code",
                    "measurement_datetime",
                    "consistency_level",
                    "survey_number",
                    "section_type",
                    "source_record_id",
                )},
                "n_vertices": len(vertices),
                "n_vertices_reported": scalars["n_vertices_reported"],
                "source": CROSS_SECTIONS_SOURCE,
            }
        )
        for order, vertex in enumerate(vertices, start=1):
            vertex_rows.append(
                {
                    "cross_section_id": cross_section_id,
                    "cross_section_vertex_id": f"{cross_section_id}_{order}",
                    "station_code": scalars["station_code"],
                    "measurement_datetime": scalars["measurement_datetime"],
                    "consistency_level": scalars["consistency_level"],
                    "survey_number": scalars["survey_number"],
                    "section_type": scalars["section_type"],
                    "vertex_order": order,
                    "vertex_distance_m": vertex["vertex_distance_m"],
                    "vertex_stage_cm": vertex["vertex_stage_cm"],
                    "source": CROSS_SECTIONS_SOURCE,
                }
            )
    empty = empty_api_cross_sections()
    return {
        "sections": pd.DataFrame(section_rows) if section_rows else empty["sections"],
        "vertices": pd.DataFrame(vertex_rows) if vertex_rows else empty["vertices"],
    }


def get_ana_cross_sections(
    station_code,
    start_date=None,
    end_date=None,
    consistency_level=None,
    token: Optional[AnaToken] = None,
    timeout: float = 120,
) -> Dict[str, pd.DataFrame]:
    """Cross-section profiles for one station (window <= 366 days)."""
    if start_date is not None and end_date is not None:
        assert_api_window(start_date, end_date)
    token = _resolve_token(token, timeout)
    response = request_json(
        CROSS_SECTIONS_ENDPOINT,
        query=_product_query(
            station_code, start_date, end_date, consistency_level, date_filter=True
        ),
        token=token,
        timeout=timeout,
    )
    return standardize_cross_sections(response)
