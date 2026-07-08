"""Tests for the deprecated pyhydroweb.core compatibility wrappers."""

import warnings
from datetime import datetime
from unittest.mock import patch

import pytest

from pyhydroweb.core import download_hidroweb_data, extract_data
from pyhydroweb.exceptions import (
    InvalidDataTypeError,
    InvalidDateFormatError,
    InvalidDateRangeError,
    InvalidOutputFormatError,
    InvalidStationCodeError,
)


class TestExtractData:
    """extract_data is deprecated but must keep its return shape."""

    def test_extract_flow_data(self, sample_xml_response):
        with pytest.warns(DeprecationWarning):
            data, consistency, dates, metadata = extract_data(sample_xml_response, 3)

        assert len(data) == 31
        assert len(consistency) == 31
        assert len(dates) == 31
        assert data[0] == 10.5
        assert data[1] == 11.2
        assert data[2] is None  # Empty value
        assert consistency[0] == 1
        # Metadata is now always empty: the EstacaoMetaDados element parsed
        # before 2.0 does not exist in real ANA responses.
        assert metadata == {}

    def test_extract_rainfall_data(self, sample_rainfall_xml):
        with pytest.warns(DeprecationWarning):
            data, consistency, dates, metadata = extract_data(sample_rainfall_xml, 2)

        # The fixture only carries Chuva01..Chuva28 columns, so 28 records
        # are returned (day 29 of February 2020 has no column in the source).
        assert len(data) == 28
        assert data[0] == 5.0
        assert data[2] is None
        assert consistency[0] == 2

    def test_invalid_data_type(self, sample_xml_response):
        with pytest.raises(InvalidDataTypeError):
            extract_data(sample_xml_response, 1)
        with pytest.raises(InvalidDataTypeError):
            extract_data(sample_xml_response, 4)

    def test_date_parsing(self, sample_xml_response):
        with pytest.warns(DeprecationWarning):
            data, consistency, dates, metadata = extract_data(sample_xml_response, 3)

        assert isinstance(dates[0], datetime)
        assert dates[0].year == 2020
        assert dates[0].month == 1
        assert dates[0].day == 1


def _legacy_response(body: str):
    return {"status": 200, "body": body, "content_type": "text/xml"}


LEGACY_BODY = """<?xml version="1.0" encoding="utf-8"?>
<HidroSerieHistorica>
  <SerieHistorica>
    <EstacaoCodigo>34879500</EstacaoCodigo>
    <NivelConsistencia>1</NivelConsistencia>
    <DataHora>2020-01-01 00:00:00</DataHora>
    <Vazao01>10.5</Vazao01>
    <Vazao02>11.2</Vazao02>
  </SerieHistorica>
</HidroSerieHistorica>
"""


class TestDownloadHidrowebData:
    """download_hidroweb_data is deprecated but must keep working over HTTPS."""

    @patch("pyhydroweb.api_daily.perform_get")
    def test_download_dataframe(self, mock_get):
        mock_get.return_value = _legacy_response(LEGACY_BODY)
        with pytest.warns(DeprecationWarning):
            result = download_hidroweb_data(34879500, data_type=3, output_format=0)

        assert result is not None
        assert len(result) == 2
        assert "flow_rate" in result.columns
        url = mock_get.call_args.kwargs["url"]
        assert url.startswith("https://telemetriaws1.ana.gov.br")
        assert "codEstacao=34879500" in url
        assert "tipoDados=3" in url

    @patch("pyhydroweb.api_daily.perform_get")
    def test_download_with_date_range(self, mock_get):
        mock_get.return_value = _legacy_response(LEGACY_BODY)
        with pytest.warns(DeprecationWarning):
            download_hidroweb_data(
                34879500,
                start_date="2020-01-01",
                end_date="2020-12-31",
                data_type=3,
                output_format=0,
            )
        url = mock_get.call_args.kwargs["url"]
        assert "dataInicio=01%2F01%2F2020" in url
        assert "dataFim=31%2F12%2F2020" in url

    def test_invalid_data_type(self):
        with pytest.raises(InvalidDataTypeError):
            download_hidroweb_data(34879500, data_type=1)

    def test_invalid_output_format(self):
        with pytest.raises(InvalidOutputFormatError):
            download_hidroweb_data(34879500, output_format=2)

    def test_invalid_station_code(self):
        with pytest.raises(InvalidStationCodeError):
            download_hidroweb_data("invalid", data_type=3)

    def test_invalid_date_format(self):
        with pytest.raises(InvalidDateFormatError):
            download_hidroweb_data(34879500, start_date="01-01-2020", data_type=3)

    def test_invalid_date_range(self):
        with pytest.raises(InvalidDateRangeError):
            download_hidroweb_data(
                34879500,
                start_date="2020-12-31",
                end_date="2020-01-01",
                data_type=3,
            )

    @patch("pyhydroweb.api_daily.perform_get")
    def test_output_format_xarray(self, mock_get):
        try:
            import xarray as xr
        except ImportError:
            pytest.skip("xarray not installed")

        mock_get.return_value = _legacy_response(LEGACY_BODY)
        with pytest.warns(DeprecationWarning):
            result = download_hidroweb_data(34879500, data_type=3, output_format=1)
        assert isinstance(result, xr.Dataset)
        assert "flow_rate" in result.variables
