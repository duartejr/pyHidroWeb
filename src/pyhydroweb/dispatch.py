"""Product/source dispatch: ``get_ana_data`` and ``get_ana_data_batch``.

Python translation of the dispatch layer in hydroDataBR's ``R/ana-main.R`` and
``R/ana-api-windowing.R`` (hydrostat/hydroDataBR, MIT).  Daily products always
come from the legacy XML route (no credentials); specialized products use the
authenticated API, with long date ranges split into <= 366-day windows.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Union

import pandas as pd

from .api_daily import get_ana_daily_series
from .api_inventory import get_ana_stations
from .api_specialized import (
    empty_api_cross_sections,
    get_ana_cross_sections,
    get_ana_discharge_measurements,
    get_ana_rating_curves,
)
from .readers import read_ana_json, read_ana_xml, read_hidroweb
from .windowing import API_MAX_WINDOW_DAYS, split_api_windows, window_n_days

PRODUCTS = (
    "daily_discharge",
    "daily_stage",
    "daily_rainfall",
    "stations",
    "discharge_measurements",
    "rating_curves",
    "cross_sections",
)

_PRODUCT_ALIASES = {
    "daily_discharge": "daily_discharge",
    "discharge": "daily_discharge",
    "vazao": "daily_discharge",
    "vazoes": "daily_discharge",
    "flow": "daily_discharge",
    "daily_stage": "daily_stage",
    "stage": "daily_stage",
    "cota": "daily_stage",
    "cotas": "daily_stage",
    "level": "daily_stage",
    "daily_rainfall": "daily_rainfall",
    "rainfall": "daily_rainfall",
    "chuva": "daily_rainfall",
    "chuvas": "daily_rainfall",
    "precipitation": "daily_rainfall",
    "precipitacao": "daily_rainfall",
    "stations": "stations",
    "inventory": "stations",
    "inventario": "stations",
    "discharge_measurements": "discharge_measurements",
    "measurements": "discharge_measurements",
    "medicoes": "discharge_measurements",
    "resumo_descarga": "discharge_measurements",
    "rating_curves": "rating_curves",
    "curves": "rating_curves",
    "curva_descarga": "rating_curves",
    "curvas": "rating_curves",
    "cross_sections": "cross_sections",
    "sections": "cross_sections",
    "perfil_transversal": "cross_sections",
    "secoes": "cross_sections",
}

_SOURCE_ALIASES = {
    "webservice": "webservice",
    "hidrowebservice": "webservice",
    "ws": "webservice",
    "legacy": "webservice",
    "api": "api",
    "authenticated_api": "api",
    "ana_api": "api",
    "hidroweb": "hidroweb",
    "file": "hidroweb",
    "csv": "hidroweb",
    "zip": "hidroweb",
    "xml": "xml",
    "json": "json",
}

_DAILY_PRODUCT_VARIABLES = {
    "daily_discharge": "discharge",
    "daily_stage": "stage",
    "daily_rainfall": "rainfall",
}


def normalize_product_name(product: str) -> str:
    """Resolve a product alias to its canonical name."""
    key = str(product).strip().lower().replace("-", "_").replace(" ", "_")
    if key not in _PRODUCT_ALIASES:
        raise ValueError(
            f"Unknown product {product!r}. Valid products: {', '.join(PRODUCTS)}."
        )
    return _PRODUCT_ALIASES[key]


def normalize_data_source_name(data_source: str) -> str:
    """Resolve a data-source alias to webservice/api/hidroweb/xml/json."""
    key = str(data_source).strip().lower().replace("-", "_").replace(" ", "_")
    if key not in _SOURCE_ALIASES:
        raise ValueError(
            f"Unknown data_source {data_source!r}. Valid sources: "
            "webservice, api, hidroweb, xml, json."
        )
    return _SOURCE_ALIASES[key]


def get_ana_data(
    product: str,
    data_source: str = "webservice",
    station_code=None,
    path=None,
    start_date=None,
    end_date=None,
    token=None,
    consistency_level=None,
    timeout: float = 60,
    **kwargs,
):
    """Acquire one ANA product for one station (or one local file).

    ``data_source``:

    - ``"webservice"`` (default) — legacy XML route, daily products only, no
      credentials required;
    - ``"api"`` — authenticated HidroWebService (stations, discharge
      measurements, rating curves, cross sections; daily products still come
      from the legacy route, matching hydroDataBR);
    - ``"hidroweb"`` / ``"xml"`` / ``"json"`` — local file at ``path``.
    """
    product = normalize_product_name(product)
    source = normalize_data_source_name(data_source)

    if source in {"hidroweb", "xml", "json"}:
        if path is None:
            raise ValueError(f"data_source={source!r} requires the path argument.")
        reader = {"hidroweb": read_hidroweb, "xml": read_ana_xml, "json": read_ana_json}[
            source
        ]
        if product in _DAILY_PRODUCT_VARIABLES:
            return reader(path, variables=_DAILY_PRODUCT_VARIABLES[product])
        return reader(path)

    if product == "stations":
        return get_ana_stations(
            station_code=station_code, token=token, timeout=timeout, **kwargs
        )

    if product in _DAILY_PRODUCT_VARIABLES:
        if station_code is None:
            raise ValueError("Daily products require station_code.")
        daily_kwargs = {"timeout": timeout}
        if consistency_level is not None:
            daily_kwargs["consistency_level"] = str(consistency_level)
        return get_ana_daily_series(
            station_code,
            _DAILY_PRODUCT_VARIABLES[product],
            start_date,
            end_date,
            **daily_kwargs,
        )

    if station_code is None:
        raise ValueError(f"Product {product!r} requires station_code.")
    fetch = {
        "discharge_measurements": get_ana_discharge_measurements,
        "rating_curves": get_ana_rating_curves,
        "cross_sections": get_ana_cross_sections,
    }[product]
    common = {
        "consistency_level": consistency_level,
        "token": token,
        "timeout": timeout,
    }
    if (
        start_date is not None
        and end_date is not None
        and window_n_days(start_date, end_date) > API_MAX_WINDOW_DAYS
    ):
        outputs = [
            fetch(station_code, window_start, window_end, **common)
            for window_start, window_end in split_api_windows(start_date, end_date)
        ]
        return _combine_window_outputs(product, outputs)
    return fetch(station_code, start_date, end_date, **common)


def _combine_window_outputs(product: str, outputs: List):
    if product == "cross_sections":
        sections = [o["sections"] for o in outputs if not o["sections"].empty]
        vertices = [o["vertices"] for o in outputs if not o["vertices"].empty]
        empty = empty_api_cross_sections()
        return {
            "sections": pd.concat(sections, ignore_index=True)
            if sections
            else empty["sections"],
            "vertices": pd.concat(vertices, ignore_index=True)
            if vertices
            else empty["vertices"],
        }
    frames = [frame for frame in outputs if frame is not None and not frame.empty]
    if not frames:
        return outputs[0] if outputs else pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates().reset_index(drop=True)


def _result_row_count(result) -> int:
    if isinstance(result, dict):
        return sum(len(frame) for frame in result.values())
    if result is None:
        return 0
    return len(result)


def get_ana_data_batch(
    product: str,
    station_codes: Sequence,
    data_source: str = "webservice",
    **kwargs,
) -> Dict[str, Union[Dict, pd.DataFrame]]:
    """Acquire one product for many stations.

    Returns ``{"results": {station_code: result}, "request_report": DataFrame}``
    where the report has one row per station with ``status`` (``success``,
    ``empty`` or ``error``), ``n_rows`` and ``message`` (redacted upstream).
    """
    if not station_codes:
        raise ValueError("station_codes must not be empty.")
    results: Dict[str, object] = {}
    report_rows = []
    for code in station_codes:
        code_text = str(code)
        try:
            result = get_ana_data(
                product, data_source=data_source, station_code=code, **kwargs
            )
            n_rows = _result_row_count(result)
            results[code_text] = result
            report_rows.append(
                {
                    "station_code": code_text,
                    "status": "success" if n_rows else "empty",
                    "success": bool(n_rows),
                    "n_rows": n_rows,
                    "message": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 - per-station fault isolation
            results[code_text] = None
            report_rows.append(
                {
                    "station_code": code_text,
                    "status": "error",
                    "success": False,
                    "n_rows": 0,
                    "message": str(exc),
                }
            )
    return {
        "results": results,
        "request_report": pd.DataFrame(
            report_rows,
            columns=["station_code", "status", "success", "n_rows", "message"],
        ),
    }
