"""Hydrometric diagnostics: daily consistency and station gauging quality.

Python translation of the diagnostic layer in hydroDataBR's ``R/diagnostics.R``
(hydrostat/hydroDataBR, MIT).  Reference data resolution follows the same
priority: user-supplied > internal package database (snapshot 2026-06) > basic
diagnostic without reference.

Note on units: daily diagnostics use the rating power law with **h0 in
meters** (``Q = a * (H_m - h0_m)^n``); analysis-level rating diagnostics use
h0 in cm — both coefficients are carried by the standardizers, mirroring the R
package.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from .analysis import measurement_diagnostics, rating_diagnostics
from .internal_data import (
    INTERNAL_SNAPSHOT,
    load_ana_discharge_measurements,
    load_ana_rating_curve_summary,
    load_ana_rating_curves,
)


def _resolve_reference(
    station_code,
    measurements: Optional[pd.DataFrame],
    rating_curves: Optional[pd.DataFrame],
    rating_curve_summary: Optional[pd.DataFrame],
    use_internal_database: bool,
) -> Dict:
    """user-supplied > internal database > none, recording source/snapshot."""
    source = "user"
    if (
        (measurements is None or measurements.empty)
        and (rating_curves is None or rating_curves.empty)
        and use_internal_database
    ):
        measurements = load_ana_discharge_measurements()
        rating_curves = load_ana_rating_curves()
        rating_curve_summary = load_ana_rating_curve_summary()
        source = "internal_database"
    if measurements is None:
        measurements = pd.DataFrame()
    if rating_curves is None:
        rating_curves = pd.DataFrame()
    if rating_curve_summary is None:
        rating_curve_summary = pd.DataFrame()
    if station_code is not None:
        codes = (
            [str(code) for code in station_code]
            if isinstance(station_code, (list, tuple, set))
            else [str(station_code)]
        )
        if not measurements.empty and "station_code" in measurements.columns:
            measurements = measurements[
                measurements["station_code"].astype(str).isin(codes)
            ]
        if not rating_curves.empty and "station_code" in rating_curves.columns:
            rating_curves = rating_curves[
                rating_curves["station_code"].astype(str).isin(codes)
            ]
        if (
            not rating_curve_summary.empty
            and "station_code" in rating_curve_summary.columns
        ):
            rating_curve_summary = rating_curve_summary[
                rating_curve_summary["station_code"].astype(str).isin(codes)
            ]
    if source == "internal_database" and measurements.empty and rating_curves.empty:
        source = "none"
    return {
        "measurements": measurements.reset_index(drop=True),
        "rating_curves": rating_curves.reset_index(drop=True),
        "rating_curve_summary": rating_curve_summary.reset_index(drop=True),
        "source": source,
        "snapshot": INTERNAL_SNAPSHOT if source == "internal_database" else None,
    }


def _predict_rating_discharge_m(stage_cm, coefficient_a, coefficient_h0_m, coefficient_n):
    """Daily-diagnostic rating prediction with h0 in meters."""
    if any(
        value is None or (isinstance(value, float) and np.isnan(value))
        for value in (stage_cm, coefficient_a, coefficient_h0_m, coefficient_n)
    ):
        return float("nan")
    base_m = float(stage_cm) / 100.0 - float(coefficient_h0_m)
    if base_m <= 0:
        return float("nan")
    return float(coefficient_a) * base_m ** float(coefficient_n)


def diagnose_daily_hydrometry(
    daily_data: pd.DataFrame,
    rating_curves: Optional[pd.DataFrame] = None,
    relative_error_threshold_pct: float = 20.0,
    measurements: Optional[pd.DataFrame] = None,
    rating_curve_summary: Optional[pd.DataFrame] = None,
    station_code=None,
    use_internal_database: bool = True,
) -> Dict:
    """Daily discharge <-> stage <-> rating-curve consistency diagnostics.

    Returns a dict with ``summary`` (one row per station), ``daily_flags``
    (one row per day with boolean ``flag_*`` columns), ``rating_matches``,
    and the resolved reference metadata (``hydrometry_reference_source`` /
    ``hydrometry_reference_snapshot``).
    """
    from .analysis import extract_daily_data
    from .contract import prefer_daily_rows

    daily = prefer_daily_rows(extract_daily_data(daily_data))
    daily = daily[daily["variable"].isin(["discharge", "stage"])]
    if station_code is not None:
        codes = (
            [str(code) for code in station_code]
            if isinstance(station_code, (list, tuple, set))
            else [str(station_code)]
        )
        daily = daily[daily["station_code"].isin(codes)]

    reference = _resolve_reference(
        station_code or (sorted(daily["station_code"].dropna().unique()) or None),
        measurements,
        rating_curves,
        rating_curve_summary,
        use_internal_database,
    )
    curves = reference["rating_curves"]

    daily_flags_frames = []
    rating_match_rows = []
    summary_rows = []
    for station, group in daily.groupby("station_code", dropna=True):
        pivot = (
            group.pivot_table(
                index="date", columns="variable", values="value", aggfunc="mean"
            )
            .reindex(columns=["discharge", "stage"])
            .reset_index()
        )
        pivot["station_code"] = station
        pivot["flag_missing_discharge"] = pivot["discharge"].isna()
        pivot["flag_missing_stage"] = pivot["stage"].isna()
        pivot["flag_discharge_without_stage"] = (
            pivot["discharge"].notna() & pivot["stage"].isna()
        )
        pivot["flag_stage_without_discharge"] = (
            pivot["stage"].notna() & pivot["discharge"].isna()
        )
        pivot["flag_non_positive_discharge"] = (pivot["discharge"] <= 0).fillna(False)
        pivot["flag_non_positive_stage"] = (pivot["stage"] <= 0).fillna(False)

        station_curves = (
            curves[curves["station_code"].astype(str) == str(station)]
            if not curves.empty and "station_code" in curves.columns
            else pd.DataFrame()
        )
        predicted = []
        relative_errors = []
        for _, day in pivot.iterrows():
            prediction = np.nan
            if not station_curves.empty and pd.notna(day["stage"]):
                timestamp = pd.Timestamp(day["date"])
                for _, segment in station_curves.iterrows():
                    valid_from = segment.get("valid_from")
                    valid_to = segment.get("valid_to")
                    if pd.notna(valid_from) and timestamp < pd.Timestamp(valid_from):
                        continue
                    if pd.notna(valid_to) and timestamp > pd.Timestamp(valid_to):
                        continue
                    low = segment.get("stage_min_cm")
                    high = segment.get("stage_max_cm")
                    if pd.notna(low) and day["stage"] < low:
                        continue
                    if pd.notna(high) and day["stage"] > high:
                        continue
                    h0_m = segment.get("coefficient_h0_m")
                    if h0_m is None or pd.isna(h0_m):
                        h0_cm = segment.get("coefficient_h0_cm")
                        h0_m = h0_cm / 100.0 if pd.notna(h0_cm) else np.nan
                    prediction = _predict_rating_discharge_m(
                        day["stage"],
                        segment.get("coefficient_a"),
                        h0_m,
                        segment.get("coefficient_n"),
                    )
                    if pd.notna(prediction):
                        break
            predicted.append(prediction)
            if (
                pd.notna(prediction)
                and prediction > 0
                and pd.notna(day["discharge"])
                and day["discharge"] > 0
            ):
                relative_errors.append(
                    100.0 * (day["discharge"] - prediction) / day["discharge"]
                )
            else:
                relative_errors.append(np.nan)
        pivot["predicted_discharge_m3s"] = predicted
        pivot["relative_error_pct"] = relative_errors
        pivot["flag_no_rating_curve_for_date"] = (
            pivot["stage"].notna() & pd.Series(predicted).isna().to_numpy()
            if not station_curves.empty
            else False
        )
        pivot["flag_relative_error_exceeds_threshold"] = (
            pivot["relative_error_pct"].abs() > relative_error_threshold_pct
        ).fillna(False)
        flag_columns = [column for column in pivot.columns if column.startswith("flag_")]
        pivot["diagnostic_problem"] = pivot[flag_columns].any(axis=1)
        daily_flags_frames.append(pivot)

        errors = pivot["relative_error_pct"].abs().dropna()
        summary_rows.append(
            {
                "station_code": station,
                "n_days": len(pivot),
                "days_with_discharge": int(pivot["discharge"].notna().sum()),
                "days_with_stage": int(pivot["stage"].notna().sum()),
                "days_with_prediction": int(
                    pd.Series(predicted).notna().sum()
                ),
                "mean_abs_relative_error_pct": float(errors.mean())
                if len(errors)
                else np.nan,
                "median_abs_relative_error_pct": float(errors.median())
                if len(errors)
                else np.nan,
                "diagnostic_problem_days": int(pivot["diagnostic_problem"].sum()),
            }
        )
        matched = pivot[pd.Series(predicted).notna().to_numpy()]
        for _, day in matched.iterrows():
            rating_match_rows.append(
                {
                    "station_code": station,
                    "date": day["date"],
                    "stage_cm": day["stage"],
                    "observed_discharge_m3s": day["discharge"],
                    "predicted_discharge_m3s": day["predicted_discharge_m3s"],
                    "relative_error_pct": day["relative_error_pct"],
                }
            )

    return {
        "summary": pd.DataFrame(summary_rows),
        "daily_flags": pd.concat(daily_flags_frames, ignore_index=True)
        if daily_flags_frames
        else pd.DataFrame(),
        "rating_matches": pd.DataFrame(rating_match_rows),
        "hydrometry_reference_summary": reference["rating_curve_summary"],
        "hydrometry_reference_source": reference["source"],
        "hydrometry_reference_snapshot": reference["snapshot"],
    }


def diagnose_station_hydrometry(
    measurements: Optional[pd.DataFrame] = None,
    rating_curves: Optional[pd.DataFrame] = None,
    detailed: bool = True,
    rating_curve_summary: Optional[pd.DataFrame] = None,
    station_code=None,
    use_internal_database: bool = True,
) -> Dict:
    """Station-level gauging and rating-curve diagnostics.

    Returns a dict with ``summary``, ``measurement_flags`` and (when
    ``detailed``) ``rating_matches`` with residual/envelope flags, plus the
    resolved reference metadata.
    """
    reference = _resolve_reference(
        station_code,
        measurements,
        rating_curves,
        rating_curve_summary,
        use_internal_database,
    )
    resolved_measurements = reference["measurements"]
    resolved_curves = reference["rating_curves"]

    measurement_flags = (
        measurement_diagnostics(resolved_measurements)
        if not resolved_measurements.empty
        else pd.DataFrame()
    )
    rating_matches = (
        rating_diagnostics(resolved_curves, resolved_measurements)
        if detailed and not resolved_curves.empty and not resolved_measurements.empty
        else pd.DataFrame()
    )

    summary_rows = []
    stations = (
        sorted(
            set(resolved_measurements.get("station_code", pd.Series(dtype=str)).dropna())
            | set(resolved_curves.get("station_code", pd.Series(dtype=str)).dropna())
        )
        if not (resolved_measurements.empty and resolved_curves.empty)
        else []
    )
    for station in stations:
        station_measurements = (
            measurement_flags[measurement_flags["station_code"] == station]
            if not measurement_flags.empty
            else pd.DataFrame()
        )
        station_matches = (
            rating_matches[rating_matches["station_code"] == station]
            if not rating_matches.empty
            else pd.DataFrame()
        )
        station_curves = (
            resolved_curves[resolved_curves["station_code"] == station]
            if not resolved_curves.empty
            else pd.DataFrame()
        )
        residuals = (
            station_matches["log_residual"].abs().dropna()
            if not station_matches.empty
            else pd.Series(dtype=float)
        )
        n_measurements = len(station_measurements)
        n_flagged = (
            int((station_measurements["n_flags"] > 0).sum()) if n_measurements else 0
        )
        outside = (
            int(station_matches["flag_outside_residual_envelope"].fillna(False).sum())
            if not station_matches.empty
            else 0
        )
        attention_score = sum(
            (
                n_flagged > 0,
                bool(len(residuals)) and float(residuals.median()) > np.log(1.25),
                bool(len(station_matches))
                and outside / max(1, len(station_matches)) > 0.10,
                station_curves.empty,
            )
        )
        summary_rows.append(
            {
                "station_code": station,
                "n_measurements": n_measurements,
                "n_flagged_measurements": n_flagged,
                "n_rating_curve_segments": len(station_curves),
                "n_rating_matches": len(station_matches),
                "median_abs_rating_log_residual": float(residuals.median())
                if len(residuals)
                else np.nan,
                "outside_residual_envelope_fraction": outside
                / max(1, len(station_matches)),
                "diagnostic_attention_score": attention_score,
                "attention_class": (
                    "high"
                    if attention_score >= 3
                    else "moderate"
                    if attention_score >= 1
                    else "low"
                ),
            }
        )

    return {
        "summary": pd.DataFrame(summary_rows),
        "measurement_flags": measurement_flags,
        "rating_matches": rating_matches,
        "hydrometry_reference_summary": reference["rating_curve_summary"],
        "hydrometry_reference_source": reference["source"],
        "hydrometry_reference_snapshot": reference["snapshot"],
    }
