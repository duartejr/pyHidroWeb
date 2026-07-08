"""Tests for the API client layer (windowing, daily, inventory, dispatch)."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from pyhydroweb.auth import AnaToken
from pyhydroweb.api_daily import get_ana_daily_series
from pyhydroweb.api_inventory import get_ana_stations, standardize_stations
from pyhydroweb.api_specialized import (
    standardize_discharge_measurements,
    standardize_rating_curves,
    standardize_cross_sections,
)
from pyhydroweb.dispatch import (
    get_ana_data,
    get_ana_data_batch,
    normalize_data_source_name,
    normalize_product_name,
)
from pyhydroweb.exceptions import ApiWindowError
from pyhydroweb.windowing import (
    assert_api_window,
    one_year_windows,
    split_api_windows,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

LEGACY_XML = (FIXTURES / "ana_daily.xml").read_text()


def _token():
    now = datetime.now()
    return AnaToken("tok", now, now + timedelta(hours=1))


class TestWindowing:
    def test_split_windows_cover_range(self):
        windows = split_api_windows("2018-01-01", "2020-12-31")
        assert windows[0][0] == date(2018, 1, 1)
        assert windows[-1][1] == date(2020, 12, 31)
        assert all((end - start).days + 1 <= 366 for start, end in windows)
        for (start_a, end_a), (start_b, _) in zip(windows, windows[1:]):
            assert (start_b - end_a).days == 1

    def test_assert_window_rejects_long_span(self):
        with pytest.raises(ApiWindowError):
            assert_api_window("2018-01-01", "2020-12-31")

    def test_assert_window_accepts_366(self):
        assert_api_window("2020-01-01", "2020-12-31")

    def test_one_year_windows(self):
        windows = one_year_windows("2018-05-10", "2020-05-09")
        assert windows[0] == (date(2018, 5, 10), date(2019, 5, 9))
        assert windows[-1][1] == date(2020, 5, 9)


class TestGetAnaDailySeries:
    @patch("pyhydroweb.api_daily.perform_get")
    def test_legacy_query_and_parse(self, mock_get):
        mock_get.return_value = {
            "status": 200,
            "body": LEGACY_XML,
            "content_type": "text/xml",
        }
        out = get_ana_daily_series(
            "01234567", "stage", "2020-01-01", "2020-12-31"
        )
        assert len(out) == 2
        assert set(out["variable"]) == {"stage"}
        url = mock_get.call_args.kwargs["url"]
        assert url.startswith("https://telemetriaws1.ana.gov.br/ServiceANA.asmx")
        assert "codEstacao=01234567" in url
        assert "dataInicio=01%2F01%2F2020" in url
        assert "tipoDados=1" in url
        assert "nivelConsistencia=2" in url

    def test_invalid_variable(self):
        with pytest.raises(ValueError):
            get_ana_daily_series("1", "temperature")

    def test_invalid_consistency(self):
        with pytest.raises(ValueError):
            get_ana_daily_series("1", "stage", consistency_level="9")


class TestInventory:
    def test_standardize_stations_fields(self):
        response = {
            "items": [
                {
                    "Codigo_Estacao": "01234567",
                    "Estacao_Nome": "FAZENDA SANTA FE",
                    "UF_Estacao": "MG",
                    "Latitude": "-19,5",
                    "Longitude": "-44,2",
                    "Altitude": "700",
                    "Area_Drenagem": "1.234,5",
                    "Tipo_Estacao": "Fluviometrica",
                    "Situacao": "1",
                }
            ]
        }
        out = standardize_stations(response)
        assert len(out) == 1
        row = out.iloc[0]
        assert row["station_code"] == "01234567"
        assert row["latitude"] == -19.5
        assert row["drainage_area_km2"] == 1234.5
        assert bool(row["operating"]) is True
        assert row["source"] == "ana_hidrowebservice_inventory"

    @patch("pyhydroweb.api_inventory.request_json")
    def test_get_ana_stations_queries_with_accented_key(self, mock_request):
        mock_request.return_value = {
            "items": [{"Codigo_Estacao": "01234567", "Estacao_Nome": "X"}]
        }
        out = get_ana_stations(station_code="01234567", token=_token())
        assert len(out) == 1
        query = mock_request.call_args.kwargs["query"]
        assert query == {"Código da Estação": "01234567"}

    def test_requires_a_filter(self):
        with pytest.raises(ValueError):
            get_ana_stations(token=_token())


class TestSpecializedStandardizers:
    def test_discharge_measurements(self):
        response = {
            "items": [
                {
                    "CodigoEstacao": "01234567",
                    "Data_Hora_Dado": "2020-03-15T10:30:00",
                    "Cota": "150,5",
                    "Vazao": "23,7",
                    "Area_Molhada": "12,3",
                    "Largura": "8,0",
                    "Vel_Media": "1,2",
                    "Nivel_Consistencia": "2",
                }
            ]
        }
        out = standardize_discharge_measurements(response)
        assert len(out) == 1
        row = out.iloc[0]
        assert row["stage_cm"] == 150.5
        assert row["discharge_m3s"] == 23.7
        assert row["measurement_datetime"].year == 2020

    def test_measurements_parent_child_merge(self):
        response = {
            "items": [
                {
                    "CodigoEstacao": "01234567",
                    "medicoes": [
                        {"Data_Hora_Dado": "2020-01-01", "Vazao": "10,0"},
                        {"Data_Hora_Dado": "2020-01-02", "Vazao": "11,0"},
                    ],
                }
            ]
        }
        out = standardize_discharge_measurements(response)
        assert len(out) == 2
        assert set(out["station_code"]) == {"01234567"}

    def test_rating_curves_with_synthesized_ids(self):
        response = {
            "items": [
                {
                    "CodigoEstacao": "01234567",
                    "DataInicio": "2010-01-01",
                    "DataFim": "2015-12-31",
                    "NumeroTrecho": "1",
                    "CotaMinima": "50",
                    "CotaMaxima": "350",
                    "CoeficienteA": "12,5",
                    "CoeficienteH0": "45",
                    "CoeficienteN": "1,8",
                }
            ]
        }
        out = standardize_rating_curves(response)
        assert len(out) == 1
        row = out.iloc[0]
        assert row["coefficient_a"] == 12.5
        assert row["coefficient_h0_cm"] == 45.0
        assert row["coefficient_h0_m"] == 0.45
        assert row["rating_curve_id"]
        assert row["rating_curve_segment_id"].endswith("_1")

    def test_cross_sections_with_packed_vertical(self):
        response = {
            "items": [
                {
                    "CodigoEstacao": "01234567",
                    "Data_Hora_Medicao": "2019-03-15T10:30:00",
                    "Num_Levantamento": "2",
                    "Tipo_Secao": "1",
                    "Vertical": "0,100|1,5,98",
                }
            ]
        }
        out = standardize_cross_sections(response)
        assert len(out["sections"]) == 1
        assert len(out["vertices"]) == 2
        assert out["vertices"].iloc[1]["vertex_distance_m"] == 1.5


class TestDispatch:
    def test_product_aliases(self):
        assert normalize_product_name("vazao") == "daily_discharge"
        assert normalize_product_name("Chuva") == "daily_rainfall"
        assert normalize_product_name("inventory") == "stations"
        with pytest.raises(ValueError):
            normalize_product_name("temperature")

    def test_source_aliases(self):
        assert normalize_data_source_name("hidrowebservice") == "webservice"
        assert normalize_data_source_name("ZIP") == "hidroweb"
        with pytest.raises(ValueError):
            normalize_data_source_name("ftp")

    def test_local_file_dispatch(self):
        out = get_ana_data(
            "daily_rainfall", data_source="json", path=FIXTURES / "ana_daily.json"
        )
        assert set(out["variable"]) == {"rainfall"}

    @patch("pyhydroweb.dispatch.get_ana_discharge_measurements")
    def test_specialized_long_range_is_windowed(self, mock_fetch):
        mock_fetch.return_value = pd.DataFrame({"station_code": ["1"]})
        get_ana_data(
            "discharge_measurements",
            data_source="api",
            station_code="1",
            start_date="2018-01-01",
            end_date="2020-12-31",
            token=_token(),
        )
        assert mock_fetch.call_count == 3

    @patch("pyhydroweb.dispatch.get_ana_daily_series")
    def test_batch_report(self, mock_daily):
        mock_daily.side_effect = [
            pd.DataFrame({"value": [1.0]}),
            RuntimeError("boom"),
        ]
        out = get_ana_data_batch("daily_discharge", ["111", "222"])
        report = out["request_report"]
        assert list(report["status"]) == ["success", "error"]
        assert out["results"]["111"] is not None
        assert out["results"]["222"] is None

    def test_batch_requires_stations(self):
        with pytest.raises(ValueError):
            get_ana_data_batch("daily_discharge", [])
