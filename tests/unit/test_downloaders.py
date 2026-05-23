"""Tests for pyhydroweb.downloaders module."""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import pandas as pd

from pyhydroweb.downloaders import (
    download_from_list,
    download_from_shape,
)
from pyhydroweb.exceptions import (
    DownloadError,
    MissingDependencyError,
)


class TestDownloadFromList:
    """Tests for download_from_list function."""

    def test_empty_stations_list(self):
        """Test that empty list raises error."""
        with pytest.raises(ValueError):
            download_from_list([])

    @patch("pyhydroweb.downloaders.pd.read_csv")
    def test_successful_download(self, mock_read_csv, tmp_path):
        """Test successful download of stations."""
        mock_df = pd.DataFrame({"value": [1, 2, 3]})
        mock_read_csv.return_value = mock_df

        download_from_list(["34879500", "34880000"], path_dir=str(tmp_path))

        assert mock_read_csv.call_count == 2
        assert (tmp_path / "34879500.csv").exists()
        assert (tmp_path / "34880000.csv").exists()

    @patch("pyhydroweb.downloaders.pd.read_csv")
    def test_automatic_stations_url(self, mock_read_csv):
        """Test correct URL construction for automatic stations."""
        mock_df = pd.DataFrame({"value": [1, 2, 3]})
        mock_read_csv.return_value = mock_df

        download_from_list(["34879500"], automatic_stations=True)

        call_args = mock_read_csv.call_args
        assert "dados-estacoes-hidro" in call_args[0][0]

    @patch("pyhydroweb.downloaders.pd.read_csv")
    def test_conventional_stations_url(self, mock_read_csv):
        """Test correct URL construction for conventional stations."""
        mock_df = pd.DataFrame({"value": [1, 2, 3]})
        mock_read_csv.return_value = mock_df

        download_from_list(
            ["34879500"],
            automatic_stations=False,
            data_type="vazoes",
            hidrologic_variable="fluviometricas",
        )

        call_args = mock_read_csv.call_args
        assert "estacoes-convencionais" in call_args[0][0]

    @patch("pyhydroweb.downloaders.pd.read_csv")
    def test_download_with_date_limits(self, mock_read_csv, tmp_path):
        """Test download with date range filter."""
        mock_df = pd.DataFrame({"value": [1, 2, 3]}, index=pd.date_range("2020-01-01", periods=3))
        mock_df.index.name = "Data Hora"
        mock_read_csv.return_value = mock_df

        download_from_list(
            ["34879500"],
            date_limits=["2020-01-01", "2020-01-02"],
            path_dir=str(tmp_path),
        )

        assert mock_read_csv.called

    @patch("pyhydroweb.downloaders.pd.read_csv")
    def test_creates_directory_if_not_exists(self, mock_read_csv, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        mock_df = pd.DataFrame({"value": [1, 2, 3]})
        mock_read_csv.return_value = mock_df

        new_dir = tmp_path / "new_dir"
        assert not new_dir.exists()

        download_from_list(["34879500"], path_dir=str(new_dir))

        assert new_dir.exists()

    @patch("pyhydroweb.downloaders.pd.read_csv")
    def test_uses_current_directory_by_default(self, mock_read_csv, tmp_path):
        """Test that current directory is used when path_dir is None."""
        mock_df = pd.DataFrame({"value": [1, 2, 3]})
        mock_read_csv.return_value = mock_df

        with patch("pyhydroweb.downloaders.os.getcwd", return_value=str(tmp_path)):
            download_from_list(["34879500"])

            assert mock_read_csv.called

    @patch("pyhydroweb.downloaders.pd.read_csv")
    def test_download_error_with_failed_stations(self, mock_read_csv):
        """Test that DownloadError is raised for failed stations."""
        mock_read_csv.side_effect = Exception("Network error")

        with pytest.raises(DownloadError):
            download_from_list(["34879500"])

    @patch("pyhydroweb.downloaders.pd.read_csv")
    def test_partial_success_with_some_failures(self, mock_read_csv, tmp_path):
        """Test handling of partial success (some stations fail)."""
        # First call succeeds, second fails
        mock_read_csv.side_effect = [
            pd.DataFrame({"value": [1, 2, 3]}),
            Exception("Network error"),
        ]

        with pytest.raises(DownloadError) as exc_info:
            download_from_list(["34879500", "34880000"], path_dir=str(tmp_path))

        assert "Failed to download" in str(exc_info.value)


class TestDownloadFromShape:
    """Tests for download_from_shape function."""

    def test_geopandas_missing(self):
        """Test error when geopandas is not available."""
        with patch("pyhydroweb.downloaders.import", side_effect=ImportError):
            with pytest.raises(MissingDependencyError):
                download_from_shape("test.shp")

    def test_shapefile_not_found(self):
        """Test error when shapefile doesn't exist."""
        with pytest.raises(FileNotFoundError):
            download_from_shape("/nonexistent/shape.shp")

    @patch("pyhydroweb.downloaders.download_from_list")
    @patch("pyhydroweb.downloaders.gpd.read_file")
    @patch("pyhydroweb.downloaders.pd.read_csv")
    @patch("pyhydroweb.downloaders.gpd.GeoDataFrame")
    @patch("pyhydroweb.downloaders.gpd.sjoin")
    def test_successful_shape_download(
        self, mock_sjoin, mock_geodf, mock_read_csv, mock_read_file, mock_download
    ):
        """Test successful download from shapefile."""
        # Mock inventory
        mock_read_csv.return_value = pd.DataFrame(
            {
                "Codigo": [1001, 1002],
                "Longitude": [-45.0, -46.0],
                "Latitude": [-15.0, -16.0],
                "TipoEstacao": ["FLU", "FLU"],
            }
        )

        # Mock shapefile
        mock_shape = MagicMock()
        mock_shape.crs = "EPSG:4326"
        mock_read_file.return_value = mock_shape

        # Mock spatial join result
        mock_result = MagicMock()
        mock_result["Codigo"].astype.return_value.to_list.return_value = ["1001", "1002"]
        mock_sjoin.return_value = mock_result

        download_from_shape("test.shp")

        mock_download.assert_called_once()

    @patch("pyhydroweb.downloaders.download_from_list")
    @patch("pyhydroweb.downloaders.gpd.read_file")
    @patch("pyhydroweb.downloaders.pd.read_csv")
    def test_shape_download_with_date_limits(
        self, mock_read_csv, mock_read_file, mock_download
    ):
        """Test shape download with date limits."""
        mock_read_csv.return_value = pd.DataFrame(
            {
                "Codigo": [1001],
                "Longitude": [-45.0],
                "Latitude": [-15.0],
                "TipoEstacao": ["FLU"],
            }
        )

        mock_shape = MagicMock()
        mock_shape.crs = "EPSG:4326"
        mock_read_file.return_value = mock_shape

        mock_result = MagicMock()
        mock_result["Codigo"].astype.return_value.to_list.return_value = ["1001"]

        with patch("pyhydroweb.downloaders.gpd.sjoin") as mock_sjoin, \
             patch("pyhydroweb.downloaders.gpd.GeoDataFrame"):
            mock_sjoin.return_value = mock_result

            download_from_shape(
                "test.shp",
                date_limits=["2020-01-01", "2020-12-31"],
            )

            call_kwargs = mock_download.call_args[1]
            assert call_kwargs["date_limits"] == ["2020-01-01", "2020-12-31"]

    @patch("pyhydroweb.downloaders.download_from_list")
    @patch("pyhydroweb.downloaders.gpd.read_file")
    @patch("pyhydroweb.downloaders.pd.read_csv")
    def test_shape_filters_fluviometric_stations(
        self, mock_read_csv, mock_read_file, mock_download
    ):
        """Test that shape download filters for fluviometric stations."""
        df = pd.DataFrame(
            {
                "Codigo": [1001, 1002, 2001],
                "Longitude": [-45.0, -46.0, -47.0],
                "Latitude": [-15.0, -16.0, -17.0],
                "TipoEstacao": ["FLU", "FLU", "PLU"],
            }
        )
        mock_read_csv.return_value = df

        mock_shape = MagicMock()
        mock_shape.crs = "EPSG:4326"
        mock_read_file.return_value = mock_shape

        mock_result = MagicMock()
        mock_result["Codigo"].astype.return_value.to_list.return_value = ["1001", "1002"]

        with patch("pyhydroweb.downloaders.gpd.sjoin") as mock_sjoin, \
             patch("pyhydroweb.downloaders.gpd.GeoDataFrame"):
            mock_sjoin.return_value = mock_result

            download_from_shape(
                "test.shp",
                hidrologic_variable="fluviometricas",
            )

            # Verify that only FLU stations are used
            mock_download.assert_called_once()
