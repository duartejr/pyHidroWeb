"""Station inventory and reference tables from the ANA HidroWebService.

Python translation of hydroDataBR's ``R/ana_reference_data.R`` and
``R/ana-reference.R`` (hydrostat/hydroDataBR, MIT).  All routes require an
authenticated token (see :func:`pyhydroweb.auth.ana_authenticate`).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import pandas as pd

from .auth import AnaToken, ana_authenticate, request_json
from .contract import (
    is_missing_token,
    normalize_name,
    normalize_station_code,
    parse_ana_date,
    parse_ana_numeric,
)

STATIONS_ENDPOINT = "/HidroInventarioEstacoes/v1"

REFERENCE_ENDPOINTS = {
    "states": "/HidroUF/v1",
    "municipalities": "/HidroMunicipio/v1",
    "basins": "/HidroBacia/v1",
    "subbasins": "/HidroSubBacia/v1",
    "rivers": "/HidroRio/v1",
    "entities": "/HidroEntidade/v1",
}

_ITEM_CONTAINER_KEYS = (
    "items",
    "data",
    "Dados",
    "dados",
    "results",
    "Results",
    "value",
    "Value",
    "content",
    "Content",
    "Estados",
    "Estado",
    "UFs",
    "Ufs",
    "UF",
    "Municipios",
    "Municipio",
    "Bacias",
    "Bacia",
    "SubBacias",
    "Sub_Bacias",
    "SubBacia",
    "Rios",
    "Rio",
    "Entidades",
    "Entidade",
)

_TRUTHY = {"1", "sim", "true", "t", "yes", "y"}
_FALSY = {"0", "nao", "não", "false", "f", "no", "n"}


def extract_items(response) -> List[Dict]:
    """Pull the list of record dicts out of an API response envelope."""
    if response is None:
        return []
    if isinstance(response, list):
        return [record for record in response if isinstance(record, dict)]
    if isinstance(response, dict):
        for key in _ITEM_CONTAINER_KEYS:
            value = response.get(key)
            if isinstance(value, list):
                return [record for record in value if isinstance(record, dict)]
            if isinstance(value, dict):
                return [value]
        return [response]
    return []


def record_value(record: Dict, candidates: Sequence[str]):
    """Look up the first matching field (exact, then normalized name)."""
    for candidate in candidates:
        if candidate in record and not is_missing_token(record[candidate]):
            return record[candidate]
    normalized = {normalize_name(key): key for key in reversed(list(record))}
    for candidate in candidates:
        key = normalized.get(normalize_name(candidate))
        if key is not None and not is_missing_token(record[key]):
            return record[key]
    return None


def _as_text(value) -> Optional[str]:
    if is_missing_token(value):
        return None
    return str(value).strip()


def _as_operating(value) -> Optional[bool]:
    text = _as_text(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in _TRUTHY:
        return True
    if lowered in _FALSY:
        return False
    return None


def _as_date(value):
    text = _as_text(value)
    if text is None:
        return None
    return parse_ana_date(text[:10])


_STATION_FIELDS = {
    "station_code": (
        ("CodigoEstacao", "Codigo_Estacao", "CodEstacao", "Codigo"),
        normalize_station_code,
    ),
    "station_name": (
        ("Estacao_Nome", "Nome_Estacao", "NomePosto", "Nome"),
        _as_text,
    ),
    "state_code": (("UF_Estacao", "Estado_Codigo", "UF", "SiglaUF"), _as_text),
    "state_name": (("UF_Nome_Estacao", "Estado_Nome", "NomeUF"), _as_text),
    "municipality_code": (("CodigoMunicipio", "Municipio_Codigo"), _as_text),
    "municipality": (("Municipio_Nome", "NomeMunicipio", "Municipio"), _as_text),
    "basin_code": (("CodigoBacia", "Bacia_Codigo"), _as_text),
    "basin_name": (("Bacia_Nome", "NomeBacia"), _as_text),
    "station_type": (("TipoEstacao", "Tipo_Estacao"), _as_text),
    "operating": (("Situacao", "Operando", "EstacaoOperando"), _as_operating),
    "latitude": (("Latitude",), parse_ana_numeric),
    "longitude": (("Longitude",), parse_ana_numeric),
    "altitude_m": (("Altitude",), parse_ana_numeric),
    "drainage_area_km2": (("AreaDrenagem", "Area_Drenagem"), parse_ana_numeric),
    "operator_code": (("CodigoOperadora", "Operadora_Codigo"), _as_text),
    "operator_acronym": (
        ("Operadora_Sigla", "SiglaOperadora", "OperadoraSigla"),
        _as_text,
    ),
    "responsible_acronym": (
        ("Responsavel_Sigla", "SiglaResponsavel", "ResponsavelSigla"),
        _as_text,
    ),
    "last_update": (("DataAtualizacao", "Data_Atualizacao"), _as_date),
}


def standardize_stations(response) -> pd.DataFrame:
    """Normalize an inventory response to the standardized station columns."""
    records = extract_items(response)
    rows = []
    for record in records:
        row = {
            column: parser(record_value(record, candidates))
            for column, (candidates, parser) in _STATION_FIELDS.items()
        }
        row["source"] = "ana_hidrowebservice_inventory"
        rows.append(row)
    columns = list(_STATION_FIELDS) + ["source"]
    if not rows:
        return pd.DataFrame(columns=columns)
    out = pd.DataFrame(rows, columns=columns)
    out = out[out["station_code"].notna()]
    return out.drop_duplicates(subset=["station_code"]).reset_index(drop=True)


def get_ana_stations(
    station_code=None,
    state_code: Optional[str] = None,
    basin_code=None,
    token: Optional[AnaToken] = None,
    timeout: float = 60,
) -> pd.DataFrame:
    """Query the station inventory route ``/HidroInventarioEstacoes/v1``.

    At least one of ``station_code``, ``state_code`` or ``basin_code`` must be
    given.  One request is issued per code; results are concatenated and
    deduplicated by ``station_code``.  Authenticates automatically from the
    environment when ``token`` is None.
    """
    if station_code is None and state_code is None and basin_code is None:
        raise ValueError(
            "Provide at least one of station_code, state_code or basin_code."
        )
    if token is None:
        token = ana_authenticate(timeout=timeout)

    queries: List[Dict[str, str]] = []
    if station_code is not None:
        codes = station_code if isinstance(station_code, (list, tuple)) else [station_code]
        queries.extend(
            {"Código da Estação": str(code)} for code in codes
        )
    if state_code is not None:
        states = state_code if isinstance(state_code, (list, tuple)) else [state_code]
        queries.extend({"UF": str(code).upper()} for code in states)
    if basin_code is not None:
        basins = basin_code if isinstance(basin_code, (list, tuple)) else [basin_code]
        queries.extend({"Código da Bacia": str(code)} for code in basins)

    frames = [
        standardize_stations(
            request_json(STATIONS_ENDPOINT, query=query, token=token, timeout=timeout)
        )
        for query in queries
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return standardize_stations(None)
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates(subset=["station_code"]).reset_index(drop=True)


def _reference_table(
    kind: str,
    columns: Dict[str, Sequence[str]],
    token: AnaToken,
    timeout: float = 60,
) -> pd.DataFrame:
    response = request_json(REFERENCE_ENDPOINTS[kind], token=token, timeout=timeout)
    records = extract_items(response)
    rows = []
    for record in records:
        row = {
            column: _as_text(record_value(record, candidates))
            for column, candidates in columns.items()
        }
        row["source"] = "ana_hidrowebservice"
        rows.append(row)
    return pd.DataFrame(rows, columns=list(columns) + ["source"])


def get_ana_states(token: AnaToken, timeout: float = 60) -> pd.DataFrame:
    """Brazilian states (UF) reference table."""
    return _reference_table(
        "states",
        {
            "state_code": ("Estado_Sigla", "SiglaUF", "SG_UF", "UF"),
            "state_name": ("Estado_Nome", "NomeUF", "Nome"),
        },
        token,
        timeout,
    )


def get_ana_municipalities(token: AnaToken, timeout: float = 60) -> pd.DataFrame:
    """Municipality reference table."""
    return _reference_table(
        "municipalities",
        {
            "municipality_code": ("Municipio_Codigo_IBGE", "CodigoMunicipio"),
            "municipality": ("Municipio_Nome", "NomeMunicipio", "Nome"),
            "state_code": ("Estado_Sigla", "SiglaUF", "UF"),
            "state_name": ("Estado_Nome", "NomeUF"),
        },
        token,
        timeout,
    )


def get_ana_basins(token: AnaToken, timeout: float = 60) -> pd.DataFrame:
    """Hydrographic basin reference table."""
    return _reference_table(
        "basins",
        {
            "basin_code": ("Bacia_Codigo", "CodigoBacia"),
            "basin_name": ("Bacia_Nome", "NomeBacia", "Nome"),
        },
        token,
        timeout,
    )


def get_ana_subbasins(token: AnaToken, timeout: float = 60) -> pd.DataFrame:
    """Hydrographic sub-basin reference table."""
    return _reference_table(
        "subbasins",
        {
            "subbasin_code": ("Sub_Bacia_Codigo", "CodigoSubBacia"),
            "subbasin_name": ("Sub_Bacia_Nome", "NomeSubBacia", "Nome"),
            "basin_code": ("Bacia_Codigo", "CodigoBacia"),
            "basin_name": ("Bacia_Nome", "NomeBacia"),
        },
        token,
        timeout,
    )


def get_ana_rivers(token: AnaToken, timeout: float = 60) -> pd.DataFrame:
    """River reference table."""
    return _reference_table(
        "rivers",
        {
            "river_code": ("Rio_Codigo", "CodigoRio"),
            "river_name": ("Rio_Nome", "NomeRio", "Nome"),
        },
        token,
        timeout,
    )


def get_ana_entities(token: AnaToken, timeout: float = 60) -> pd.DataFrame:
    """Operating/responsible entity reference table."""
    return _reference_table(
        "entities",
        {
            "entity_code": ("Entidade_Codigo", "CodigoEntidade"),
            "entity_name": ("Entidade_Nome", "NomeEntidade", "Nome"),
            "entity_acronym": ("Entidade_Sigla", "SiglaEntidade", "Sigla"),
        },
        token,
        timeout,
    )
