"""Tests for pyhydroweb.metadata module."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from pyhydroweb.metadata import (
    get_station_metadata,
    get_cached_inventory,
    download_station_inventory,
    get_all_stations,
    get_stations_in_bounds,
    get_nearby_stations,
)
from pyhydroweb.exceptions import DownloadError, MissingDependencyError


@pytest.fixture
def sample_inventory():
    """Create sample station inventory data."""
    return pd.DataFrame(
        {
            "Codigo": ["34879500", "34880000", "40006000"],
            "Nome": ["Rio Paraná near Itaipu", "Rio Paraná de Campos", "Rio Araguaia"],
            "Latitude": [-25.5, -23.0, -15.0],
            "Longitude": [-54.5, -47.0, -52.0],
            "Altitude": [150.0, 200.0, 250.0],
            "TipoEstacao": ["FLU", "FLU", "FLU"],
            "ResponsavelTecnico": ["ANA", "ANA", "ANA"],
        }
    )


class TestGetAllStations:
    """Tests for get_all_stations function."""

    @patch("pyhydroweb.metadata.get_cached_inventory")
    def test_get_all_stations(self, mock_get_inventory, sample_inventory):
        """Test retrieving all stations."""
        mock_get_inventory.return_value = sample_inventory

        result = get_all_stations()

        assert len(result) == 3
        assert all(code in result["Codigo"].values for code in ["34879500", "34880000", "40006000"])

    @patch("pyhydroweb.metadata.get_cached_inventory")
    def test_filter_by_station_type(self, mock_get_inventory, sample_inventory):
        """Test filtering stations by type."""
        mock_get_inventory.return_value = sample_inventory

        result = get_all_stations(station_type="FLU")

        assert len(result) == 3
        assert all(t == "FLU" for t in result["TipoEstacao"])


class TestGetStationMetadata:
    """Tests for get_station_metadata function."""

    @patch("pyhydroweb.metadata.get_cached_inventory")
    def test_get_existing_station(self, mock_get_inventory, sample_inventory):
        """Test retrieving metadata for existing station."""
        mock_get_inventory.return_value = sample_inventory

        result = get_station_metadata("34879500")

        assert result is not None
        assert result["Nome"] == "Rio Paraná near Itaipu"
        assert result["Latitude"] == -25.5
        assert result["Longitude"] == -54.5

    @patch("pyhydroweb.metadata.get_cached_inventory")
    def test_get_nonexistent_station(self, mock_get_inventory, sample_inventory):
        """Test retrieving metadata for nonexistent station."""
        mock_get_inventory.return_value = sample_inventory

        result = get_station_metadata("99999999")

        assert result is None


class TestGetStationsInBounds:
    """Tests for get_stations_in_bounds function."""

    @patch("pyhydroweb.metadata.get_cached_inventory")
    def test_stations_in_bounds(self, mock_get_inventory, sample_inventory):
        """Test getting stations within geographic bounds."""
        mock_get_inventory.return_value = sample_inventory

        result = get_stations_in_bounds(
            min_lat=-26, max_lat=-25, min_lon=-55, max_lon=-54
        )

        assert len(result) == 1
        assert result.iloc[0]["Codigo"] == "34879500"

    @patch("pyhydroweb.metadata.get_cached_inventory")
    def test_stations_in_bounds_with_type_filter(self, mock_get_inventory, sample_inventory):
        """Test getting stations in bounds with type filter."""
        mock_get_inventory.return_value = sample_inventory

        result = get_stations_in_bounds(
            min_lat=-26, max_lat=-15, min_lon=-55, max_lon=-45, station_type="FLU"
        )

        assert len(result) > 0
        assert all(t == "FLU" for t in result["TipoEstacao"])

    @patch("pyhydroweb.metadata.get_cached_inventory")
    def test_no_stations_in_bounds(self, mock_get_inventory, sample_inventory):
        """Test when no stations exist in bounds."""
        mock_get_inventory.return_value = sample_inventory

        result = get_stations_in_bounds(
            min_lat=0, max_lat=5, min_lon=0, max_lon=5
        )

        assert len(result) == 0


class TestGetNearbyStations:
    """Tests for get_nearby_stations function."""

    @patch("pyhydroweb.metadata.get_cached_inventory")
    def test_nearby_stations(self, mock_get_inventory, sample_inventory):
        """Test getting nearby stations."""
        mock_get_inventory.return_value = sample_inventory

        result = get_nearby_stations(-25.5, -54.5, radius_km=1000)

        assert len(result) > 0
        assert "distance_km" in result.columns
        # Check if sorted by distance
        assert result["distance_km"].is_monotonic_increasing

    @patch("pyhydroweb.metadata.get_cached_inventory")
    def test_nearby_stations_small_radius(self, mock_get_inventory, sample_inventory):
        """Test nearby stations with small radius."""
        mock_get_inventory.return_value = sample_inventory

        result = get_nearby_stations(-25.5, -54.5, radius_km=1)

        assert len(result) == 1
        assert result.iloc[0]["Codigo"] == "34879500"

    @patch("pyhydroweb.metadata.get_cached_inventory")
    def test_nearby_stations_with_type_filter(self, mock_get_inventory, sample_inventory):
        """Test nearby stations with type filter."""
        mock_get_inventory.return_value = sample_inventory

        result = get_nearby_stations(-25.5, -54.5, radius_km=5000, station_type="FLU")

        assert all(t == "FLU" for t in result["TipoEstacao"])


class TestGetStationsInPolygon:
    """Tests for get_stations_in_polygon function."""

    def test_stations_in_polygon_missing_geopandas(self):
        """Test error when geopandas is missing."""
        try:
            import geopandas  # noqa
            pytest.skip("geopandas is installed")
        except ImportError:
            from pyhydroweb.metadata import get_stations_in_polygon
            with pytest.raises(MissingDependencyError):
                get_stations_in_polygon([(-26, -55), (-25, -54)])

    def test_stations_in_polygon(self):
        """Test getting stations within polygon."""
        try:
            import geopandas  # noqa
        except ImportError:
            pytest.skip("geopandas not installed")

        with patch("pyhydroweb.metadata.get_cached_inventory") as mock_get_inventory:
            sample_df = pd.DataFrame(
                {
                    "Codigo": ["34879500", "34880000"],
                    "Nome": ["Station 1", "Station 2"],
                    "Latitude": [-25.5, -23.0],
                    "Longitude": [-54.5, -47.0],
                }
            )
            mock_get_inventory.return_value = sample_df

            polygon = [(-26, -55), (-26, -54), (-25, -54), (-25, -55)]
            result = get_stations_in_polygon(polygon)

            assert "geometry" not in result.columns  # Geometry column should be removed


class TestDownloadStationInventory:
    """Tests for download_station_inventory function."""

    @patch("requests.get")
    def test_download_inventory_success(self, mock_get):
        """Test successful inventory download."""
        import io
        import zipfile

        # Create a mock zip file with CSV
        mock_csv = "Codigo;Nome;Latitude;Longitude;Altitude\n34879500;Test Station;-25.5;-54.5;150.0\n"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("inventario.csv", mock_csv)
        zip_buffer.seek(0)

        mock_response = MagicMock()
        mock_response.content = zip_buffer.getvalue()
        mock_get.return_value = mock_response

        result = download_station_inventory()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["Codigo"] == "34879500"

    @patch("requests.get")
    def test_download_inventory_connection_error(self, mock_get):
        """Test handling of connection errors."""
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with pytest.raises(DownloadError):
            download_station_inventory()

    @patch("requests.get")
    def test_download_inventory_bad_zip(self, mock_get):
        """Test handling of invalid zip file."""
        mock_response = MagicMock()
        mock_response.content = b"not a zip file"
        mock_get.return_value = mock_response

        with pytest.raises(DownloadError):
            download_station_inventory()
