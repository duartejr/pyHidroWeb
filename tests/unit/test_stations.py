"""Tests for pyhydroweb.stations and pyhydroweb.internal_data."""

import hashlib
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from pyhydroweb.exceptions import ChecksumMismatchError
from pyhydroweb.internal_data import (
    DATASETS,
    download_ana_cross_section_vertices,
    load_ana_stations,
    load_internal,
)
from pyhydroweb.stations import filter_ana_stations, station_has_product


class TestInternalData:
    def test_stations_snapshot_shape(self):
        stations = load_ana_stations()
        assert stations.shape == (37584, 27)
        assert "station_code" in stations.columns
        assert "latitude" in stations.columns

    def test_all_datasets_load(self):
        for name in DATASETS:
            frame = load_internal(name)
            assert not frame.empty

    def test_unknown_dataset(self):
        with pytest.raises(ValueError):
            load_internal("nope")

    def test_load_returns_copy(self):
        first = load_ana_stations()
        first["station_code"] = "mutated"
        second = load_ana_stations()
        assert (second["station_code"] != "mutated").any()


class TestFilterAnaStations:
    def test_filter_by_state(self):
        out = filter_ana_stations(state_code="pa")
        assert not out.empty
        assert set(out["state_code"].str.upper()) == {"PA"}

    def test_filter_by_product_discharge(self):
        out = filter_ana_stations(product="discharge")
        assert not out.empty
        assert len(out) < 37584

    def test_filter_by_discharge_measurements_flag(self):
        out = filter_ana_stations(product="discharge_measurements")
        assert not out.empty
        assert out["has_discharge_measurements"].all()

    def test_filter_by_name_pattern(self):
        out = filter_ana_stations(name_pattern="salin")
        assert not out.empty
        assert out["station_name"].str.contains("SALIN", case=False).all()

    def test_filter_combination(self):
        out = filter_ana_stations(state_code="MG", product=["discharge"])
        assert not out.empty
        assert set(out["state_code"]) == {"MG"}

    def test_invalid_product(self):
        with pytest.raises(ValueError):
            filter_ana_stations(product="temperature")

    def test_custom_station_data(self):
        custom = pd.DataFrame(
            {
                "station_code": ["1", "2"],
                "station_name": ["A", "B"],
                "state_code": ["MG", "SP"],
                "is_operating": [True, False],
            }
        )
        out = filter_ana_stations(custom, is_operating=True)
        assert list(out["station_code"]) == ["1"]

    def test_station_has_product_missing_column(self):
        with pytest.raises(ValueError):
            station_has_product(pd.DataFrame({"x": [1]}), "discharge")


class TestDownloadVertices:
    def test_wrong_version_rejected(self):
        with pytest.raises(ValueError):
            download_ana_cross_section_vertices(version="1999-01")

    @patch("requests.get")
    def test_checksum_mismatch_removes_file(self, mock_get, tmp_path):
        payload = b"fake rds content"
        data_response = MagicMock(status_code=200, content=payload)
        data_response.raise_for_status = MagicMock()
        meta_response = MagicMock(
            status_code=200, text="sha256\n" + "0" * 64 + "\n"
        )
        meta_response.raise_for_status = MagicMock()
        mock_get.side_effect = [data_response, meta_response]
        with pytest.raises(ChecksumMismatchError):
            download_ana_cross_section_vertices(path=tmp_path, read=False)
        assert not any(tmp_path.iterdir())

    @patch("requests.get")
    def test_checksum_pass_returns_path(self, mock_get, tmp_path):
        payload = b"fake rds content"
        digest = hashlib.sha256(payload).hexdigest()
        data_response = MagicMock(status_code=200, content=payload)
        data_response.raise_for_status = MagicMock()
        meta_response = MagicMock(status_code=200, text=f"sha256\n{digest}\n")
        meta_response.raise_for_status = MagicMock()
        mock_get.side_effect = [data_response, meta_response]
        result = download_ana_cross_section_vertices(path=tmp_path, read=False)
        assert result.is_file()

    @patch("requests.get")
    def test_metadata_failure_refuses_by_default(self, mock_get, tmp_path):
        payload = b"fake rds content"
        data_response = MagicMock(status_code=200, content=payload)
        data_response.raise_for_status = MagicMock()
        import requests as requests_module

        mock_get.side_effect = [
            data_response,
            requests_module.exceptions.ConnectionError("no metadata"),
        ]
        with pytest.raises(ChecksumMismatchError):
            download_ana_cross_section_vertices(path=tmp_path, read=False)
