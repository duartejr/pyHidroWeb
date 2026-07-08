"""Tests for pyhydroweb.analysis, diagnostics, tables and output."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from pyhydroweb.analysis import analyze_hydro_data, rating_curve_discharge
from pyhydroweb.diagnostics import (
    diagnose_daily_hydrometry,
    diagnose_station_hydrometry,
)
from pyhydroweb.output import write_hydro_data
from pyhydroweb.tables import table_hydro_data


def _daily(values, variable="discharge", station="1", start=date(2020, 1, 1)):
    unit = {"discharge": "m3/s", "stage": "cm", "rainfall": "mm"}[variable]
    return pd.DataFrame(
        {
            "station_code": station,
            "date": [start + timedelta(days=i) for i in range(len(values))],
            "variable": variable,
            "value": values,
            "unit": unit,
            "consistency_level": "2",
            "source_status": None,
            "source": "test",
        }
    )


@pytest.fixture
def two_years_discharge():
    rng = np.random.RandomState(42)
    values = list(10 + 5 * rng.rand(731))
    return _daily(values, start=date(2019, 1, 1))


class TestAvailabilityAndStatistics:
    def test_full_year_availability(self):
        daily = _daily([1.0] * 366, start=date(2020, 1, 1))
        out = analyze_hydro_data(daily, "daily_availability")
        assert out.iloc[0]["availability_pct"] == 100.0
        assert out.iloc[0]["days_expected"] == 366

    def test_missing_days_counted(self):
        values = [1.0] * 20 + [None] * 5 + [1.0] * 6
        daily = _daily(values)
        out = analyze_hydro_data(daily, "daily_availability", period="monthly")
        assert out.iloc[0]["days_missing"] == 5
        assert out.iloc[0]["availability_pct"] == pytest.approx(100 * 26 / 31)

    def test_daily_statistics(self):
        daily = _daily([1.0, 2.0, 3.0, 4.0])
        out = analyze_hydro_data(daily, "daily_statistics")
        row = out.iloc[0]
        assert row["mean_value"] == 2.5
        assert row["min_value"] == 1.0
        assert row["max_value"] == 4.0
        assert row["median_value"] == 2.5


class TestFlowDuration:
    def test_weibull_positions_and_interpolation(self):
        # 9 values 1..9 -> empirical exceedance of rank k is 100k/10
        daily = _daily([float(v) for v in range(9, 0, -1)])
        out = analyze_hydro_data(
            daily, "flow_duration", exceedance_probabilities=[10, 50, 90]
        )
        by_p = out.set_index("permanence_pct")["value"]
        assert by_p[10] == 9.0  # rank 1 -> P=10%
        assert by_p[50] == 5.0  # rank 5 -> P=50%
        assert by_p[90] == 1.0  # rank 9 -> P=90%

    def test_monotonically_decreasing(self, two_years_discharge):
        out = analyze_hydro_data(two_years_discharge, "flow_duration")
        assert out["value"].is_monotonic_decreasing


class TestFlowIndices:
    def test_q90_q95_type8(self):
        values = [float(v) for v in range(1, 101)]
        daily = _daily(values, start=date(2020, 1, 1))
        out = analyze_hydro_data(daily, "flow_indices")
        row = out.iloc[0]
        assert row["qmlt"] == 50.5
        expected_q90 = float(np.quantile(values, 0.10, method="median_unbiased"))
        expected_q95 = float(np.quantile(values, 0.05, method="median_unbiased"))
        assert row["q90"] == pytest.approx(expected_q90)
        assert row["q95"] == pytest.approx(expected_q95)
        assert row["q95"] < row["q90"] < row["qmlt"]


class TestAnnualMaximaAndLowFlows:
    def test_annual_maxima_rank(self, two_years_discharge):
        out = analyze_hydro_data(
            two_years_discharge, "annual_maxima", complete_years_only=False
        )
        assert set(out["analysis_year"]) == {2019, 2020}
        assert set(out["rank_descending"]) == {1, 2}

    def test_gap_near_max_flag(self):
        values = [1.0] * 100 + [None, None, 50.0] + [1.0] * 262
        daily = _daily(values, start=date(2020, 1, 1))
        out = analyze_hydro_data(daily, "annual_maxima", complete_years_only=False)
        assert bool(out.iloc[0]["flag_gap_near_max"])

    def test_low_flows_q7(self):
        values = [10.0] * 100 + [2.0] * 7 + [10.0] * 259
        daily = _daily(values, start=date(2020, 1, 1))
        out = analyze_hydro_data(daily, "low_flows", durations=[7])
        row = out.iloc[0]
        assert row["min_value"] == pytest.approx(2.0)
        assert row["duration"] == 7

    def test_low_flow_windows_require_full_validity(self):
        values = [10.0, None] * 15  # no fully-valid 7-day window
        daily = _daily(values, start=date(2020, 1, 1))
        out = analyze_hydro_data(daily, "low_flows", durations=[7])
        assert out.empty


class TestRainfallIndices:
    def test_etccdi_indices(self):
        values = (
            [0.0] * 25          # long dry run (CDD = 25 at start)
            + [15.0] * 3        # 3 wet days >= 10 (r10)
            + [60.0]            # rx1day = 60, r50
            + [0.5] * 2         # below wet threshold -> dry days
        )
        daily = _daily(values, variable="rainfall", start=date(2020, 1, 1))
        out = analyze_hydro_data(daily, "rainfall_indices")
        row = out.iloc[0]
        assert row["rx1day"] == 60.0
        assert row["r10"] == 4
        assert row["r50"] == 1
        assert row["wet_days"] == 4
        assert row["cdd"] == 25
        assert row["cwd"] == 4
        assert row["sdii"] == pytest.approx((15 * 3 + 60) / 4)

    def test_rx5day_rolling_sum(self):
        values = [0.0] * 10 + [10.0, 20.0, 30.0, 20.0, 10.0] + [0.0] * 16
        daily = _daily(values, variable="rainfall", start=date(2020, 1, 1))
        out = analyze_hydro_data(daily, "rainfall_indices")
        assert out.iloc[0]["rx5day"] == 90.0


class TestRainfallDiagnostics:
    def test_flags(self):
        values = [0.0] * 30 + [500.0] + [1.0] * 5
        daily = _daily(values, variable="rainfall", start=date(2020, 1, 1))
        out = analyze_hydro_data(daily, "rainfall_diagnostics")
        assert not out.empty
        assert out["flag_very_high_rainfall"].any()
        assert out["flag_long_zero_sequence"].any()


class TestRatingCurve:
    def test_power_law(self):
        # Q = 2 * (150 - 50)^1.5 with h0 in cm
        assert rating_curve_discharge(150, 2.0, 50.0, 1.5) == pytest.approx(
            2.0 * 100**1.5
        )

    def test_below_h0_is_nan(self):
        assert np.isnan(rating_curve_discharge(40, 2.0, 50.0, 1.5))


class TestDiagnostics:
    def _curves(self):
        return pd.DataFrame(
            {
                "station_code": ["1"],
                "rating_curve_id": ["c1"],
                "rating_curve_segment_id": ["c1_1"],
                "valid_from": [date(2019, 1, 1)],
                "valid_to": [date(2021, 12, 31)],
                "consistency_level": ["2"],
                "segment_number": [1],
                "stage_min_cm": [50.0],
                "stage_max_cm": [400.0],
                "coefficient_a": [2.0],
                "coefficient_h0_cm": [50.0],
                "coefficient_h0_m": [0.5],
                "coefficient_n": [1.5],
            }
        )

    def test_daily_hydrometry_consistent_data(self):
        stage = _daily([150.0] * 10, variable="stage")
        predicted = 2.0 * ((150.0 / 100.0) - 0.5) ** 1.5
        discharge = _daily([predicted] * 10, variable="discharge")
        daily = pd.concat([stage, discharge], ignore_index=True)
        result = diagnose_daily_hydrometry(
            daily, rating_curves=self._curves(), use_internal_database=False
        )
        summary = result["summary"].iloc[0]
        assert summary["days_with_prediction"] == 10
        assert summary["mean_abs_relative_error_pct"] == pytest.approx(0.0, abs=1e-9)
        assert not result["daily_flags"]["flag_relative_error_exceeds_threshold"].any()

    def test_daily_hydrometry_detects_error(self):
        stage = _daily([150.0] * 10, variable="stage")
        discharge = _daily([100.0] * 10, variable="discharge")  # way off
        daily = pd.concat([stage, discharge], ignore_index=True)
        result = diagnose_daily_hydrometry(
            daily, rating_curves=self._curves(), use_internal_database=False
        )
        assert result["daily_flags"]["flag_relative_error_exceeds_threshold"].all()

    def test_station_hydrometry_with_user_data(self):
        measurements = pd.DataFrame(
            {
                "station_code": ["1", "1", "1"],
                "measurement_datetime": pd.to_datetime(
                    ["2020-01-01", "2020-06-01", "2020-12-01"]
                ),
                "measurement_date": [date(2020, 1, 1), date(2020, 6, 1), date(2020, 12, 1)],
                "stage_cm": [100.0, 150.0, -5.0],
                "discharge_m3s": [10.0, 20.0, 5.0],
            }
        )
        result = diagnose_station_hydrometry(
            measurements=measurements,
            rating_curves=self._curves(),
            use_internal_database=False,
        )
        assert len(result["summary"]) == 1
        flags = result["measurement_flags"]
        assert flags["flag_stage_non_positive"].sum() == 1
        assert result["hydrometry_reference_source"] == "user"

    def test_internal_database_reference(self):
        result = diagnose_station_hydrometry(station_code="34879500")
        assert result["hydrometry_reference_source"] in {"internal_database", "none"}


class TestTables:
    def test_analysis_tables_route(self):
        daily = _daily([1.0] * 31)
        out = table_hydro_data(daily, "daily_availability")
        assert not out.empty

    def test_station_products(self):
        out = table_hydro_data(None, "station_products", station_code="34879500")
        assert not out.empty
        assert set(out["product"]) == {
            "daily_discharge",
            "daily_stage",
            "daily_rainfall",
            "telemetry",
            "discharge_measurements",
        }

    def test_unknown_table(self):
        with pytest.raises(ValueError):
            table_hydro_data(None, "nope")


class TestWriteHydroData:
    def test_single_csv(self, tmp_path):
        daily = _daily([1.0, 2.0])
        written = write_hydro_data(daily, tmp_path / "out.csv")
        assert written["data"].exists()
        assert pd.read_csv(written["data"]).shape[0] == 2

    def test_directory_with_manifest(self, tmp_path):
        components = {
            "daily": _daily([1.0]),
            "stats": pd.DataFrame({"a": [1]}),
        }
        written = write_hydro_data(
            components, tmp_path / "export", manifest=True
        )
        assert (tmp_path / "export" / "daily.csv").exists()
        assert (tmp_path / "export" / "hydro_export_manifest.csv").exists()

    def test_sensitive_columns_scrubbed(self, tmp_path):
        table = pd.DataFrame({"value": [1], "senha": ["x"], "api_token": ["y"]})
        written = write_hydro_data(table, tmp_path / "out.csv")
        exported = pd.read_csv(written["data"])
        assert list(exported.columns) == ["value"]

    def test_refuses_overwrite(self, tmp_path):
        daily = _daily([1.0])
        write_hydro_data(daily, tmp_path / "out.csv")
        with pytest.raises(FileExistsError):
            write_hydro_data(daily, tmp_path / "out.csv")

    def test_parquet_format(self, tmp_path):
        daily = _daily([1.0, 2.0])
        written = write_hydro_data(daily, tmp_path / "out.parquet")
        assert pd.read_parquet(written["data"]).shape[0] == 2
