"""Tests for the deprecated pyhydroweb.downloaders compatibility wrappers."""

from unittest.mock import patch

import pandas as pd
import pytest

from pyhydroweb.downloaders import download_from_list, download_from_shape
from pyhydroweb.exceptions import DownloadError, MissingDependencyError


def _batch(results):
    report = pd.DataFrame(
        {
            "station_code": list(results),
            "status": [
                "success" if frame is not None and not frame.empty else "error"
                for frame in results.values()
            ],
            "success": [
                frame is not None and not frame.empty for frame in results.values()
            ],
            "n_rows": [0 if frame is None else len(frame) for frame in results.values()],
            "message": [None] * len(results),
        }
    )
    return {"results": results, "request_report": report}


class TestDownloadFromList:
    def test_empty_stations_list(self):
        with pytest.raises(ValueError):
            with pytest.warns(DeprecationWarning):
                download_from_list([])

    @patch("pyhydroweb.downloaders.get_ana_data_batch")
    def test_successful_download(self, mock_batch, tmp_path):
        frame = pd.DataFrame({"value": [1.0, 2.0]})
        mock_batch.return_value = _batch({"34879500": frame, "34880000": frame})

        with pytest.warns(DeprecationWarning):
            download_from_list(["34879500", "34880000"], path_dir=str(tmp_path))

        assert (tmp_path / "34879500.csv").exists()
        assert (tmp_path / "34880000.csv").exists()

    @patch("pyhydroweb.downloaders.get_ana_data_batch")
    def test_data_type_mapped_to_product(self, mock_batch, tmp_path):
        mock_batch.return_value = _batch({"1": pd.DataFrame({"value": [1.0]})})
        with pytest.warns(DeprecationWarning):
            download_from_list(["1"], data_type="vazoes", path_dir=str(tmp_path))
        assert mock_batch.call_args.args[0] == "daily_discharge"

    @patch("pyhydroweb.downloaders.get_ana_data_batch")
    def test_date_limits_forwarded(self, mock_batch, tmp_path):
        mock_batch.return_value = _batch({"1": pd.DataFrame({"value": [1.0]})})
        with pytest.warns(DeprecationWarning):
            download_from_list(
                ["1"],
                date_limits=["2020-01-01", "2020-01-31"],
                path_dir=str(tmp_path),
            )
        kwargs = mock_batch.call_args.kwargs
        assert kwargs["start_date"] == "2020-01-01"
        assert kwargs["end_date"] == "2020-01-31"

    @patch("pyhydroweb.downloaders.get_ana_data_batch")
    def test_creates_directory_if_not_exists(self, mock_batch, tmp_path):
        mock_batch.return_value = _batch({"1": pd.DataFrame({"value": [1.0]})})
        new_dir = tmp_path / "new_dir"
        with pytest.warns(DeprecationWarning):
            download_from_list(["1"], path_dir=str(new_dir))
        assert new_dir.exists()

    @patch("pyhydroweb.downloaders.get_ana_data_batch")
    def test_download_error_with_failed_stations(self, mock_batch, tmp_path):
        mock_batch.return_value = _batch({"1": None})
        with pytest.raises(DownloadError):
            with pytest.warns(DeprecationWarning):
                download_from_list(["1"], path_dir=str(tmp_path))

    @patch("pyhydroweb.downloaders.get_ana_data_batch")
    def test_partial_success_reports_failed(self, mock_batch, tmp_path):
        mock_batch.return_value = _batch(
            {"1": pd.DataFrame({"value": [1.0]}), "2": None}
        )
        with pytest.raises(DownloadError) as excinfo:
            with pytest.warns(DeprecationWarning):
                download_from_list(["1", "2"], path_dir=str(tmp_path))
        assert "2" in str(excinfo.value)
        assert (tmp_path / "1.csv").exists()


class TestDownloadFromShape:
    def test_geopandas_missing(self):
        try:
            import geopandas  # noqa: F401

            pytest.skip("geopandas is installed")
        except ImportError:
            with pytest.raises(MissingDependencyError):
                with pytest.warns(DeprecationWarning):
                    download_from_shape("test.shp")

    def test_shapefile_not_found(self):
        try:
            import geopandas  # noqa: F401
        except ImportError:
            pytest.skip("geopandas not installed")
        with pytest.raises(FileNotFoundError):
            with pytest.warns(DeprecationWarning):
                download_from_shape("/nonexistent/shape.shp")
