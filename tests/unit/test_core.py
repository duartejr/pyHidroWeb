"""Tests for pyhydroweb.core module."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from pyhydroweb.core import extract_data, download_hidroweb_data
from pyhydroweb.exceptions import (
    InvalidDataTypeError,
    InvalidOutputFormatError,
    DataParsingError,
    DownloadError,
    MissingDependencyError,
)


class TestExtractData:
    """Tests for extract_data function."""

    def test_extract_flow_data(self, sample_xml_response):
        """Test extraction of flow (Vazão) data."""
        data, consistency, dates = extract_data(sample_xml_response, 3)

        assert len(data) == 31
        assert len(consistency) == 31
        assert len(dates) == 31
        assert data[0] == 10.5
        assert data[1] == 11.2
        assert data[2] is None  # Empty value
        assert consistency[0] == 1

    def test_extract_rainfall_data(self, sample_rainfall_xml):
        """Test extraction of rainfall (Chuva) data."""
        data, consistency, dates = extract_data(sample_rainfall_xml, 2)

        assert len(data) == 29  # February 2020 has 29 days (leap year)
        assert len(consistency) == 29
        assert len(dates) == 29
        assert data[0] == 5.0
        assert data[2] is None
        assert consistency[0] == 2

    def test_invalid_data_type(self, sample_xml_response):
        """Test that invalid data type raises error."""
        with pytest.raises(InvalidDataTypeError):
            extract_data(sample_xml_response, 1)

        with pytest.raises(InvalidDataTypeError):
            extract_data(sample_xml_response, 4)

    def test_date_parsing(self, sample_xml_response):
        """Test that dates are parsed correctly."""
        data, consistency, dates = extract_data(sample_xml_response, 3)

        assert isinstance(dates[0], datetime)
        assert dates[0].year == 2020
        assert dates[0].month == 1
        assert dates[0].day == 1

    def test_consistency_levels_preserved(self, sample_xml_response):
        """Test that consistency levels are preserved for all days."""
        data, consistency, dates = extract_data(sample_xml_response, 3)

        assert all(c == 1 for c in consistency)


class TestDownloadHidrowebData:
    """Tests for download_hidroweb_data function."""

    @patch("pyhydroweb.core.requests.get")
    def test_download_successful(self, mock_get, mock_api_response):
        """Test successful data download."""
        mock_get.return_value = mock_api_response

        result = download_hidroweb_data(34879500, data_type=3, output_format=0)

        assert result is not None
        assert len(result) == 31
        assert "flow_rate" in result.columns

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[1]["params"]["codEstacao"] == 34879500
        assert call_args[1]["params"]["tipoDados"] == 3

    @patch("pyhydroweb.core.requests.get")
    def test_download_with_date_range(self, mock_get, mock_api_response):
        """Test download with date range."""
        mock_get.return_value = mock_api_response

        result = download_hidroweb_data(
            34879500, start_date="2020-01-01", end_date="2020-12-31", data_type=3, output_format=0
        )

        call_args = mock_get.call_args
        assert call_args[1]["params"]["dataInicio"] == "2020-01-01"
        assert call_args[1]["params"]["dataFim"] == "2020-12-31"

    @patch("pyhydroweb.core.requests.get")
    def test_download_rainfall_data(self, mock_get, mock_api_response):
        """Test downloading rainfall data."""
        mock_get.return_value = mock_api_response

        result = download_hidroweb_data(34879500, data_type=2, output_format=0)

        call_args = mock_get.call_args
        assert call_args[1]["params"]["tipoDados"] == 2

    def test_invalid_data_type(self):
        """Test that invalid data type is rejected."""
        with pytest.raises(InvalidDataTypeError):
            download_hidroweb_data(34879500, data_type=1)

    def test_invalid_output_format(self):
        """Test that invalid output format is rejected."""
        with pytest.raises(InvalidOutputFormatError):
            download_hidroweb_data(34879500, output_format=2)

    def test_invalid_station_code(self):
        """Test that invalid station code is rejected."""
        with pytest.raises(Exception):  # InvalidStationCodeError
            download_hidroweb_data("invalid", data_type=3)

    @patch("pyhydroweb.core.requests.get")
    def test_api_connection_error(self, mock_get):
        """Test handling of API connection errors."""
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with pytest.raises(DownloadError):
            download_hidroweb_data(34879500, data_type=3)

    @patch("pyhydroweb.core.requests.get")
    def test_api_timeout_error(self, mock_get):
        """Test handling of API timeout."""
        import requests

        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")

        with pytest.raises(DownloadError):
            download_hidroweb_data(34879500, data_type=3)

    @patch("pyhydroweb.core.requests.get")
    def test_xarray_missing_dependency(self, mock_get, mock_api_response):
        """Test error when xarray is not available."""
        mock_get.return_value = mock_api_response

        # This test would only work if xarray is not installed
        # We skip it if xarray is available
        try:
            import xarray  # noqa
            pytest.skip("xarray is installed, cannot test missing dependency")
        except ImportError:
            with pytest.raises(MissingDependencyError):
                download_hidroweb_data(34879500, output_format=1)

    @patch("pyhydroweb.core.requests.get")
    def test_output_format_dataframe(self, mock_get, mock_api_response):
        """Test output as pandas DataFrame."""
        mock_get.return_value = mock_api_response

        result = download_hidroweb_data(34879500, output_format=0)

        import pandas as pd

        assert isinstance(result, pd.DataFrame)
        assert "flow_rate" in result.columns

    @patch("pyhydroweb.core.requests.get")
    def test_output_format_xarray(self, mock_get, mock_api_response):
        """Test output as xarray Dataset."""
        try:
            import xarray as xr
        except ImportError:
            pytest.skip("xarray not installed")

        mock_get.return_value = mock_api_response
        result = download_hidroweb_data(34879500, output_format=1)

        assert isinstance(result, xr.Dataset)
        assert "flow_rate" in result.variables

    @patch("pyhydroweb.core.requests.get")
    def test_data_attributes_xarray(self, mock_get, mock_api_response):
        """Test that xarray Dataset has proper attributes."""
        try:
            import xarray as xr
        except ImportError:
            pytest.skip("xarray not installed")

        mock_get.return_value = mock_api_response
        result = download_hidroweb_data(34879500, output_format=1)

        assert result["flow_rate"].attrs["units"] == "m$\\,$s$^{-1}$"
        assert "Flow" in result["flow_rate"].attrs["long_name"]

    def test_invalid_date_format(self):
        """Test that invalid date format is rejected."""
        from pyhydroweb.exceptions import InvalidDateFormatError

        with pytest.raises(InvalidDateFormatError):
            download_hidroweb_data(34879500, start_date="01-01-2020", data_type=3)

    def test_invalid_date_range(self):
        """Test that invalid date range is rejected."""
        from pyhydroweb.exceptions import InvalidDateRangeError

        with pytest.raises(InvalidDateRangeError):
            download_hidroweb_data(
                34879500,
                start_date="2020-12-31",
                end_date="2020-01-01",
                data_type=3,
            )

    @patch("pyhydroweb.core.requests.get")
    def test_consistency_level_parameter(self, mock_get, mock_api_response):
        """Test that consistency level is properly passed to API."""
        mock_get.return_value = mock_api_response

        download_hidroweb_data(34879500, consistency_level=1, data_type=3, output_format=0)

        call_args = mock_get.call_args
        assert call_args[1]["params"]["nivelConsistencia"] == 1
