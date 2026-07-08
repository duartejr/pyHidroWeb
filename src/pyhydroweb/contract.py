"""Standardized daily data contract for Brazilian hydrological series.

Python translation of hydroDataBR's ``R/daily-contract.R`` (hydrostat/hydroDataBR,
MIT).  Every reader and API route in this package normalizes its output into the
same 8-column daily contract so analysis, plotting and export code can stay
source-neutral.
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date, datetime
from typing import Iterable, List, Optional, Sequence, Union

import pandas as pd

#: Canonical column order of the standardized daily series.
DAILY_CONTRACT_COLUMNS = [
    "station_code",
    "date",
    "variable",
    "value",
    "unit",
    "consistency_level",
    "source_status",
    "source",
]

#: Tokens treated as missing values throughout ANA/HidroWeb sources.
MISSING_TOKENS = {"", "NA", "NaN", "NULL", "null", "None", "none"}

#: Daily variables supported by the contract.
DAILY_VARIABLES = ("discharge", "stage", "rainfall")

#: ANA wide-column prefix -> (variable, unit).
VARIABLE_SPECS = {
    "Vazao": ("discharge", "m3/s"),
    "Cota": ("stage", "cm"),
    "Chuva": ("rainfall", "mm"),
}

#: Date formats tried, in order, when parsing ANA date strings.
DATE_FORMATS = (
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%Y%m%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y/%m/%d %H:%M:%S",
)

_STATION_CANDIDATES = (
    "station_code",
    "EstacaoCodigo",
    "CodigoEstacao",
    "CodigoDaEstacao",
    "CodEstacao",
    "codigoestacao",
)
_DATE_CANDIDATES = ("date", "Data", "DataHora", "Data_Hora_Dado", "DataHoraDado")
_CONSISTENCY_CANDIDATES = (
    "consistency_level",
    "NivelConsistencia",
    "Nivel_Consistencia",
    "Consistencia",
)

# Long-format (API item) candidates — see hydroDataBR daily-contract.R lines 401-404.
API_DATE_CANDIDATES = (
    "date",
    "Data",
    "DataMedicao",
    "Data_Medicao",
    "DataHora",
    "DataHoraMedicao",
    "Data_Hora_Medicao",
    "Dia",
)
API_STATION_CANDIDATES = (
    "station_code",
    "CodEstacao",
    "CodigoEstacao",
    "codigo_estacao",
    "EstacaoCodigo",
    "Codigo",
)
API_CONSISTENCY_CANDIDATES = (
    "consistency_level",
    "NivelConsistencia",
    "nivel_consistencia",
    "Consistencia",
    "Nivel",
)
API_STATUS_CANDIDATES = ("source_status", "status", "Status")
API_VALUE_CANDIDATES = {
    "stage": ("Cota", "cota", "stage", "ValorCota", "valor_cota", "value", "Valor"),
    "rainfall": (
        "Chuva",
        "chuva",
        "rainfall",
        "Precipitacao",
        "precipitacao",
        "ValorChuva",
        "value",
        "Valor",
    ),
    "discharge": (
        "Vazao",
        "vazao",
        "discharge",
        "ValorVazao",
        "valor_vazao",
        "value",
        "Valor",
    ),
}


def is_missing_token(value) -> bool:
    """Return True when ``value`` is one of the ANA missing-value tokens."""
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    return str(value).strip() in MISSING_TOKENS


def normalize_name(name) -> str:
    """Normalize a column name for fuzzy matching (ASCII, lowercase, alnum only)."""
    if name is None:
        return ""
    text = unicodedata.normalize("NFKD", str(name))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]", "", text)


def normalize_station_code(value) -> Optional[str]:
    """Normalize a station code: strip, drop trailing ``.0``, missing -> None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if text in MISSING_TOKENS:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    return text


def parse_ana_numeric(value) -> Optional[float]:
    """Parse an ANA numeric token, handling Brazilian formats.

    ``"1.234,56"`` -> 1234.56, ``"12,3"`` -> 12.3, missing tokens -> None.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None if pd.isna(value) else float(value)
    text = re.sub(r"\s+", "", str(value))
    if text in MISSING_TOKENS:
        return None
    if "." in text and "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_ana_date(value) -> Optional[date]:
    """Parse an ANA date token trying the fixed list of formats in order."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.date()
    text = str(value).strip()
    if text in MISSING_TOKENS:
        return None
    text = text.replace("T", " ")
    text = re.sub(r"\.\d+", "", text)
    text = re.sub(r"Z$", "", text).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def empty_daily_series() -> pd.DataFrame:
    """Return an empty DataFrame with the daily-contract columns and dtypes."""
    return pd.DataFrame(
        {
            "station_code": pd.Series(dtype="object"),
            "date": pd.Series(dtype="object"),
            "variable": pd.Series(dtype="object"),
            "value": pd.Series(dtype="float64"),
            "unit": pd.Series(dtype="object"),
            "consistency_level": pd.Series(dtype="object"),
            "source_status": pd.Series(dtype="object"),
            "source": pd.Series(dtype="object"),
        }
    )


def find_first_column(
    data: pd.DataFrame, candidates: Sequence[str]
) -> Optional[str]:
    """Find the first matching column: exact match first, then normalized match."""
    columns = list(data.columns)
    for candidate in candidates:
        if candidate in columns:
            return candidate
    normalized = {normalize_name(col): col for col in reversed(columns)}
    for candidate in candidates:
        key = normalize_name(candidate)
        if key in normalized:
            return normalized[key]
    return None


def match_daily_variables(
    variables: Union[str, Sequence[str], None]
) -> List[str]:
    """Validate/expand the ``variables`` argument of the readers.

    Accepts ``"all"``, ``"discharge"``, ``"stage"``, ``"rainfall"`` (or a
    sequence of them); ``"all"``/None expands to every variable.
    """
    if variables is None:
        return list(DAILY_VARIABLES)
    if isinstance(variables, str):
        variables = [variables]
    result: List[str] = []
    for item in variables:
        name = str(item).strip().lower()
        if name == "all":
            return list(DAILY_VARIABLES)
        if name not in DAILY_VARIABLES:
            raise ValueError(
                "variables must be 'all', 'discharge', 'stage' or 'rainfall'; "
                f"got {item!r}"
            )
        if name not in result:
            result.append(name)
    if not result:
        return list(DAILY_VARIABLES)
    return result


def filter_daily_variables(
    data: pd.DataFrame, variables: Sequence[str]
) -> pd.DataFrame:
    """Keep only rows whose ``variable`` is in ``variables``."""
    if data.empty:
        return data
    return data[data["variable"].isin(list(variables))].reset_index(drop=True)


def keep_daily_contract(data: pd.DataFrame) -> pd.DataFrame:
    """Coerce an arbitrary frame into the 8-column daily contract."""
    out = data.copy()
    for column in DAILY_CONTRACT_COLUMNS:
        if column not in out.columns:
            out[column] = None
    out = out[DAILY_CONTRACT_COLUMNS]
    out["station_code"] = out["station_code"].map(normalize_station_code)
    out["date"] = out["date"].map(parse_ana_date)
    out["value"] = out["value"].map(parse_ana_numeric)
    for column in ("variable", "unit", "consistency_level", "source_status", "source"):
        out[column] = out[column].map(
            lambda v: None if is_missing_token(v) else str(v)
        )
    return out.reset_index(drop=True)


def prefer_daily_rows(data: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate to one row per (station, date, variable).

    Preference order: consistency ``"2"`` (consisted) over ``"1"`` (raw) over
    anything else; then non-missing values over missing; then original order.
    """
    if data.empty:
        return data
    out = data.copy()
    out = out[
        out["date"].notna()
        & out["station_code"].notna()
        & out["variable"].notna()
        & (out["variable"] != "")
    ].copy()
    if out.empty:
        return out.reset_index(drop=True)

    def consistency_priority(level) -> int:
        if level == "2":
            return 1
        if level == "1":
            return 2
        return 3

    out["_consistency_priority"] = out["consistency_level"].map(consistency_priority)
    out["_value_priority"] = out["value"].map(lambda v: 2 if pd.isna(v) else 1)
    out["_order"] = range(len(out))
    out = out.sort_values(
        ["station_code", "date", "variable", "_consistency_priority", "_value_priority", "_order"],
        kind="stable",
    )
    out = out.drop_duplicates(subset=["station_code", "date", "variable"], keep="first")
    out = out.sort_values(["station_code", "date", "variable"], kind="stable")
    return out.drop(columns=["_consistency_priority", "_value_priority", "_order"]).reset_index(
        drop=True
    )


def _make_month_day_date(month_anchor: Optional[date], day: int) -> Optional[date]:
    """Combine a month-anchor date with a day-of-month, dropping impossible days."""
    if month_anchor is None:
        return None
    last_day = calendar.monthrange(month_anchor.year, month_anchor.month)[1]
    if day < 1 or day > last_day:
        return None
    return date(month_anchor.year, month_anchor.month, day)


def _extract_daily_columns(columns: Iterable[str], prefix: str):
    """Yield ``(column_name, day)`` for wide per-day value columns of ``prefix``."""
    pattern = re.compile(rf"^{prefix}_?([0-9]{{2}})$", re.IGNORECASE)
    for column in columns:
        match = pattern.match(str(column))
        if match:
            yield column, int(match.group(1))


def _find_daily_status_column(
    columns: Sequence[str], prefix: str, day: int
) -> Optional[str]:
    """Locate the companion ``*Status`` column for a per-day value column."""
    day_text = f"{day:02d}"
    candidates = (
        f"{prefix}{day_text}Status",
        f"{prefix}_{day_text}Status",
        f"{prefix}{day_text}_Status",
        f"{prefix}_{day_text}_Status",
    )
    lookup = {str(c).lower(): c for c in columns}
    for candidate in candidates:
        found = lookup.get(candidate.lower())
        if found is not None:
            return found
    return None


def standardize_ana_daily_table(
    data: pd.DataFrame,
    source_label: str,
    merge_consistency: bool = True,
) -> pd.DataFrame:
    """Normalize an ANA table (wide monthly or already-long) into the contract.

    Mirrors hydroDataBR's ``.standardize_ana_daily_table``: if the input already
    carries the contract key columns it is passed through ``keep_daily_contract``;
    otherwise the wide ``Vazao01..31`` / ``Cota01..31`` / ``Chuva01..31`` layout
    is exploded into one row per station/date/variable.
    """
    if data is None or data.empty:
        return empty_daily_series()

    contract_keys = {"station_code", "date", "variable", "value"}
    if contract_keys.issubset(set(data.columns)):
        out = keep_daily_contract(data)
        if "source" in data.columns and data["source"].notna().any():
            pass
        else:
            out["source"] = source_label
        if merge_consistency:
            out = prefer_daily_rows(out)
        return out

    station_col = find_first_column(data, _STATION_CANDIDATES)
    date_col = find_first_column(data, _DATE_CANDIDATES)
    consistency_col = find_first_column(data, _CONSISTENCY_CANDIDATES)

    if station_col is None or date_col is None:
        raise ValueError(
            "Could not find station/date columns in the ANA table "
            f"(columns: {list(data.columns)!r})."
        )

    columns = list(data.columns)
    records = []
    for _, row in data.iterrows():
        station = normalize_station_code(row[station_col])
        month_anchor = parse_ana_date(row[date_col])
        consistency = None
        if consistency_col is not None and not is_missing_token(row[consistency_col]):
            consistency = str(row[consistency_col]).strip()
            if consistency.endswith(".0"):
                consistency = consistency[:-2]
        for prefix, (variable, unit) in VARIABLE_SPECS.items():
            for column, day in _extract_daily_columns(columns, prefix):
                observation_date = _make_month_day_date(month_anchor, day)
                if observation_date is None:
                    continue
                status_col = _find_daily_status_column(columns, prefix, day)
                status = None
                if status_col is not None and not is_missing_token(row[status_col]):
                    status = str(row[status_col]).strip()
                records.append(
                    {
                        "station_code": station,
                        "date": observation_date,
                        "variable": variable,
                        "value": parse_ana_numeric(row[column]),
                        "unit": unit,
                        "consistency_level": consistency,
                        "source_status": status,
                        "source": source_label,
                    }
                )

    if not records:
        return empty_daily_series()
    out = pd.DataFrame.from_records(records, columns=DAILY_CONTRACT_COLUMNS)
    if merge_consistency:
        out = prefer_daily_rows(out)
    else:
        out = out.sort_values(
            ["station_code", "date", "variable"], kind="stable"
        ).reset_index(drop=True)
    return out


def standardize_api_daily_items(
    items,
    variable: str,
    source_label: str = "ANA API",
    merge_consistency: bool = True,
) -> pd.DataFrame:
    """Normalize long-format (one row per day) ANA API items into the contract.

    Mirrors hydroDataBR's ``ana_standardize_api_daily_items``: recognizes the
    richer candidate field lists used by the authenticated API and defaults
    ``source_status`` to ``"success"`` when absent.
    """
    if variable not in DAILY_VARIABLES:
        raise ValueError(f"variable must be one of {DAILY_VARIABLES}; got {variable!r}")
    data = items_to_data_frame(items)
    if data is None or data.empty:
        return empty_daily_series()

    station_col = find_first_column(data, API_STATION_CANDIDATES)
    date_col = find_first_column(data, API_DATE_CANDIDATES)
    value_col = find_first_column(data, API_VALUE_CANDIDATES[variable])
    consistency_col = find_first_column(data, API_CONSISTENCY_CANDIDATES)
    status_col = find_first_column(data, API_STATUS_CANDIDATES)
    if date_col is None or value_col is None:
        return empty_daily_series()

    unit = {"discharge": "m3/s", "stage": "cm", "rainfall": "mm"}[variable]
    out = pd.DataFrame(
        {
            "station_code": data[station_col].map(normalize_station_code)
            if station_col is not None
            else None,
            "date": data[date_col].map(parse_ana_date),
            "variable": variable,
            "value": data[value_col].map(parse_ana_numeric),
            "unit": unit,
            "consistency_level": data[consistency_col].map(
                lambda v: None if is_missing_token(v) else str(v).strip()
            )
            if consistency_col is not None
            else None,
            "source_status": data[status_col].map(
                lambda v: "success" if is_missing_token(v) else str(v).strip()
            )
            if status_col is not None
            else "success",
            "source": source_label,
        }
    )
    out = out[DAILY_CONTRACT_COLUMNS]
    if merge_consistency:
        out = prefer_daily_rows(out)
    return out


def items_to_data_frame(items) -> Optional[pd.DataFrame]:
    """Convert an API response payload into a DataFrame.

    Accepts a DataFrame, a list of records, or a dict with an ``items`` or
    ``data`` container (mirrors ``ana_daily_items_to_data_frame``).
    """
    if items is None:
        return None
    if isinstance(items, pd.DataFrame):
        return items
    if isinstance(items, dict):
        for key in ("items", "data"):
            if key in items and items[key] is not None:
                return items_to_data_frame(items[key])
        return pd.DataFrame([items])
    if isinstance(items, list):
        if not items:
            return None
        return pd.DataFrame([r for r in items if isinstance(r, dict)])
    return None


def require_daily_data(data: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Raise if the standardized frame carries no daily records."""
    if data is None or data.empty:
        raise ValueError(
            f"No daily records were recognized in {source_name}. "
            "Check that the file matches an ANA HidroSerieHistorica/HidroWeb layout."
        )
    return data
