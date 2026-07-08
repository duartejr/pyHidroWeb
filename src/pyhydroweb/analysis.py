"""Hydrological analyses over the standardized daily contract.

Python translation of hydroDataBR's ``R/analyze-daily.R`` and
``R/analyze-hydro.R`` (hydrostat/hydroDataBR, MIT).  All analyses complete each
station/variable group to a full daily calendar first, so missing dates count
as gaps.

Quantile conventions (ported exactly from the R package):

- flow-duration curves interpolate linearly on Weibull plotting positions;
- flow indices (Q90/Q95) use R quantile type 8 (= numpy ``median_unbiased``);
- daily summaries (q25/q75) use R type 7 (= numpy ``linear``).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from .contract import DAILY_VARIABLES, prefer_daily_rows

ANALYSES = (
    "daily_statistics",
    "daily_availability",
    "flow_duration",
    "flow_indices",
    "monthly_flow_indices",
    "rainfall_indices",
    "annual_maxima",
    "rainfall_annual_maxima",
    "low_flows",
    "daily_gap_summary",
    "rainfall_diagnostics",
)

MONTH_LABELS_PT = (
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
)


def extract_daily_data(data) -> pd.DataFrame:
    """Pull a daily-contract frame out of a frame, acquisition dict or batch."""
    if isinstance(data, pd.DataFrame):
        return data
    if isinstance(data, dict):
        for key in ("daily_data", "data", "daily_discharge", "daily_stage", "daily_rainfall"):
            value = data.get(key)
            if isinstance(value, pd.DataFrame) and not value.empty:
                return value
        results = data.get("results")
        if isinstance(results, dict):
            frames = [
                frame for frame in results.values() if isinstance(frame, pd.DataFrame)
            ]
            if frames:
                return pd.concat(frames, ignore_index=True)
    raise TypeError("Could not find standardized daily data in the input object.")


def analysis_year(dates: pd.Series, year_start_month: int = 1) -> pd.Series:
    """Analysis-year label: hydrological years are labeled by the ending year."""
    years = dates.map(lambda d: d.year)
    if year_start_month == 1:
        return years
    months = dates.map(lambda d: d.month)
    return years + (months >= year_start_month).astype(int)


def _complete_daily_calendar(group: pd.DataFrame) -> pd.DataFrame:
    """Reindex a station/variable group to every day of its date span."""
    group = group.dropna(subset=["date"]).copy()
    if group.empty:
        return group
    start, end = min(group["date"]), max(group["date"])
    calendar = pd.DataFrame(
        {"date": [start + timedelta(days=i) for i in range((end - start).days + 1)]}
    )
    merged = calendar.merge(
        group.drop_duplicates(subset=["date"]), on="date", how="left"
    )
    for column in ("station_code", "variable", "unit", "source"):
        if column in group.columns and group[column].notna().any():
            merged[column] = group[column].dropna().iloc[0]
    return merged


def _groups(daily: pd.DataFrame):
    for (station, variable), group in daily.groupby(
        ["station_code", "variable"], dropna=False, sort=True
    ):
        yield station, variable, group.sort_values("date")


def _quantile(values: np.ndarray, probability: float, method: str) -> float:
    if len(values) == 0:
        return float("nan")
    return float(np.quantile(values, probability, method=method))


# ---------------------------------------------------------------------------
# Availability / statistics / gaps
# ---------------------------------------------------------------------------

def daily_availability(
    daily: pd.DataFrame, period: str = "annual"
) -> pd.DataFrame:
    """Expected/observed/valid day counts and availability percentage.

    ``period`` is ``"annual"`` or ``"monthly"``; availability is
    ``100 * days_with_value / days_expected`` over the complete calendar.
    """
    if period not in {"annual", "monthly"}:
        raise ValueError("period must be 'annual' or 'monthly'.")
    rows = []
    for station, variable, group in _groups(daily):
        completed = _complete_daily_calendar(group)
        if completed.empty:
            continue
        keys = completed["date"].map(
            (lambda d: f"{d.year:04d}") if period == "annual" else (lambda d: f"{d.year:04d}-{d.month:02d}")
        )
        for key, chunk in completed.groupby(keys):
            expected = len(chunk)
            with_value = int(chunk["value"].notna().sum())
            rows.append(
                {
                    "station_code": station,
                    "variable": variable,
                    "period": key,
                    "days_expected": expected,
                    "days_with_value": with_value,
                    "days_missing": expected - with_value,
                    "availability_pct": 100.0 * with_value / expected,
                    "missing_pct": 100.0 * (expected - with_value) / expected,
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "station_code",
            "variable",
            "period",
            "days_expected",
            "days_with_value",
            "days_missing",
            "availability_pct",
            "missing_pct",
        ],
    )


def daily_statistics(daily: pd.DataFrame, period: str = "annual") -> pd.DataFrame:
    """Per-period mean/min/max/total plus availability columns."""
    availability = daily_availability(daily, period=period)
    rows = []
    for station, variable, group in _groups(daily):
        completed = _complete_daily_calendar(group)
        if completed.empty:
            continue
        keys = completed["date"].map(
            (lambda d: f"{d.year:04d}") if period == "annual" else (lambda d: f"{d.year:04d}-{d.month:02d}")
        )
        for key, chunk in completed.groupby(keys):
            values = chunk["value"].dropna().to_numpy(dtype=float)
            rows.append(
                {
                    "station_code": station,
                    "variable": variable,
                    "period": key,
                    "days_with_value": len(values),
                    "mean_value": float(values.mean()) if len(values) else np.nan,
                    "min_value": float(values.min()) if len(values) else np.nan,
                    "max_value": float(values.max()) if len(values) else np.nan,
                    "q25": _quantile(values, 0.25, "linear"),
                    "median_value": _quantile(values, 0.50, "linear"),
                    "q75": _quantile(values, 0.75, "linear"),
                    "total_value": float(values.sum()) if len(values) else np.nan,
                }
            )
    statistics = pd.DataFrame(rows)
    if statistics.empty:
        return statistics
    return statistics.merge(
        availability[
            ["station_code", "variable", "period", "days_expected", "availability_pct"]
        ],
        on=["station_code", "variable", "period"],
        how="left",
    )


def daily_gap_summary(daily: pd.DataFrame, period: str = "monthly") -> pd.DataFrame:
    """Missing-day counts per period, plus zero-or-negative day counts."""
    rows = []
    for station, variable, group in _groups(daily):
        completed = _complete_daily_calendar(group)
        if completed.empty:
            continue
        keys = completed["date"].map(
            (lambda d: f"{d.year:04d}") if period == "annual" else (lambda d: f"{d.year:04d}-{d.month:02d}")
        )
        for key, chunk in completed.groupby(keys):
            n_days = len(chunk)
            n_values = int(chunk["value"].notna().sum())
            zero_or_negative = int((chunk["value"].dropna() <= 0).sum())
            rows.append(
                {
                    "station_code": station,
                    "variable": variable,
                    "period": key,
                    "n_days": n_days,
                    "n_values": n_values,
                    "missing_days": n_days - n_values,
                    "missing_pct": 100.0 * (n_days - n_values) / n_days,
                    "zero_or_negative_days": zero_or_negative,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Flow duration and indices
# ---------------------------------------------------------------------------

def flow_duration(
    daily: pd.DataFrame,
    exceedance_probabilities: Sequence[int] = tuple(range(1, 100)),
) -> pd.DataFrame:
    """Flow-duration curve via Weibull plotting positions.

    Values are sorted descending; the empirical exceedance probability of the
    ``rank``-th value is ``100 * rank / (n + 1)``; requested percentiles are
    linearly interpolated (constant extrapolation at the ends).
    """
    probabilities = sorted(
        {min(99, max(1, int(probability))) for probability in exceedance_probabilities}
    )
    rows = []
    for station, variable, group in _groups(daily):
        values = group["value"].dropna().to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if len(values) == 0:
            continue
        ordered = np.sort(values)[::-1]
        n = len(ordered)
        empirical = 100.0 * (np.arange(1, n + 1) / (n + 1))
        for probability in probabilities:
            interpolated = float(
                np.interp(probability, empirical, ordered)
            )
            rows.append(
                {
                    "station_code": station,
                    "variable": variable,
                    "permanence_pct": probability,
                    "exceedance_probability": probability,
                    "non_exceedance_probability": 100 - probability,
                    "value": interpolated,
                    "n_values": n,
                    "interpolation_method": "linear_empirical_fdc",
                }
            )
    return pd.DataFrame(rows)


def flow_indices(daily: pd.DataFrame) -> pd.DataFrame:
    """QMLT (long-term mean), Q90 and Q95 per station/variable.

    Q90/Q95 are the flows exceeded 90 %/95 % of the time, i.e. the 0.10/0.05
    quantiles of the flow distribution, computed with R quantile type 8.
    """
    rows = []
    for station, variable, group in _groups(daily):
        completed = _complete_daily_calendar(group)
        values = completed["value"].dropna().to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        rows.append(
            {
                "station_code": station,
                "variable": variable,
                "qmlt": float(values.mean()) if len(values) else np.nan,
                "q90": _quantile(values, 0.10, "median_unbiased"),
                "q95": _quantile(values, 0.05, "median_unbiased"),
                "min_value": float(values.min()) if len(values) else np.nan,
                "max_value": float(values.max()) if len(values) else np.nan,
                "n_days": len(completed),
                "n_values": len(values),
                "missing_days": len(completed) - len(values),
            }
        )
    return pd.DataFrame(rows)


def monthly_flow_indices(daily: pd.DataFrame) -> pd.DataFrame:
    """QMLT/Q90/Q95 per calendar month across all years (discharge only)."""
    discharge = daily[daily["variable"] == "discharge"]
    rows = []
    for (station, month), group in discharge.dropna(subset=["date"]).groupby(
        ["station_code", discharge.dropna(subset=["date"])["date"].map(lambda d: d.month)]
    ):
        values = group["value"].dropna().to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        rows.append(
            {
                "station_code": station,
                "month": month,
                "month_label": MONTH_LABELS_PT[month - 1],
                "qmlt_month": float(values.mean()) if len(values) else np.nan,
                "q90_month": _quantile(values, 0.10, "median_unbiased"),
                "q95_month": _quantile(values, 0.05, "median_unbiased"),
                "n_values": len(values),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Annual maxima and low flows
# ---------------------------------------------------------------------------

def _iqr_outlier_flags(values: pd.Series) -> pd.Series:
    """IQR outlier flags across years (3x IQR beyond Q25/Q75, type 8, >=5 values)."""
    finite = values.dropna()
    if len(finite) < 5:
        return pd.Series(False, index=values.index)
    array = finite.to_numpy(dtype=float)
    q25 = _quantile(array, 0.25, "median_unbiased")
    q75 = _quantile(array, 0.75, "median_unbiased")
    iqr = q75 - q25
    upper, lower = q75 + 3 * iqr, q25 - 3 * iqr
    return values.map(lambda v: bool(pd.notna(v) and (v > upper or v < lower)))


def annual_maxima(
    daily: pd.DataFrame,
    year_start_month: int = 1,
    complete_years_only: bool = True,
    valid_fraction_threshold: float = 0.90,
    gap_window_days: int = 3,
) -> pd.DataFrame:
    """Annual maxima with quality flags and a descending rank for frequency fits."""
    rows = []
    for station, variable, group in _groups(daily):
        completed = _complete_daily_calendar(group)
        if completed.empty:
            continue
        completed = completed.copy()
        completed["analysis_year"] = analysis_year(
            completed["date"], year_start_month
        )
        for year, chunk in completed.groupby("analysis_year"):
            values = chunk["value"]
            n_valid = int(values.notna().sum())
            expected = len(chunk)
            if n_valid == 0:
                continue
            completeness = 100.0 * n_valid / expected
            if complete_years_only and n_valid < expected:
                partial = True
            else:
                partial = False
            max_value = float(values.max())
            max_dates = chunk.loc[values == max_value, "date"]
            max_date = max_dates.iloc[0]
            gap_near_max = bool(
                chunk[
                    chunk["date"].map(
                        lambda d: abs((d - max_date).days) <= gap_window_days
                    )
                ]["value"]
                .isna()
                .any()
            )
            rows.append(
                {
                    "station_code": station,
                    "variable": variable,
                    "analysis_year": int(year),
                    "max_value": max_value,
                    "max_date": max_date,
                    "n_days_equal_to_max": int(len(max_dates)),
                    "completeness_pct": completeness,
                    "flag_partial_year": partial,
                    "flag_few_valid_days": (n_valid / expected) < valid_fraction_threshold,
                    "flag_gap_near_max": gap_near_max,
                    "flag_tied_max_within_year": len(max_dates) > 1,
                    "flag_zero_maximum": max_value == 0.0,
                    "flag_negative_values_year": bool((values.dropna() < 0).any()),
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["flag_iqr_outlier"] = False
    for (_, _), index in out.groupby(["station_code", "variable"]).groups.items():
        out.loc[index, "flag_iqr_outlier"] = _iqr_outlier_flags(
            out.loc[index, "max_value"]
        )
    flag_columns = [column for column in out.columns if column.startswith("flag_")]
    out["n_flags"] = out[flag_columns].sum(axis=1).astype(int)
    out["rank_descending"] = (
        out.groupby(["station_code", "variable"])["max_value"]
        .rank(ascending=False, method="min")
        .astype(int)
    )
    return out


def low_flows(
    daily: pd.DataFrame,
    year_start_month: int = 1,
    durations: Sequence[int] = (1, 3, 7, 15, 30),
    valid_window_fraction_threshold: float = 0.80,
) -> pd.DataFrame:
    """Annual minima of ``duration``-day rolling means (the Q7,10 family).

    Rolling means only use fully-valid windows; annual minima get an ascending
    rank across years for frequency analysis.
    """
    rows = []
    for station, variable, group in _groups(daily):
        completed = _complete_daily_calendar(group)
        if completed.empty:
            continue
        completed = completed.copy()
        completed["analysis_year"] = analysis_year(
            completed["date"], year_start_month
        )
        values = completed["value"].to_numpy(dtype=float)
        for duration in durations:
            rolling = (
                pd.Series(values).rolling(window=duration, min_periods=duration).mean()
            )
            completed[f"_rolling_{duration}"] = rolling.to_numpy()
        for year, chunk in completed.groupby("analysis_year"):
            for duration in durations:
                windows = chunk[f"_rolling_{duration}"]
                n_expected = len(chunk)
                n_valid = int(windows.notna().sum())
                if n_valid == 0:
                    continue
                min_index = windows.idxmin()
                min_value = float(windows.loc[min_index])
                min_end_date = chunk.loc[min_index, "date"]
                min_start_date = min_end_date - timedelta(days=duration - 1)
                rows.append(
                    {
                        "station_code": station,
                        "variable": variable,
                        "analysis_year": int(year),
                        "duration": int(duration),
                        "min_value": min_value,
                        "min_start_date": min_start_date,
                        "min_end_date": min_end_date,
                        "month_minimum": min_end_date.month,
                        "month_minimum_label": MONTH_LABELS_PT[min_end_date.month - 1],
                        "n_windows_expected": n_expected,
                        "n_valid_windows": n_valid,
                        "windows_valid_pct": 100.0 * n_valid / n_expected,
                        "flag_few_valid_windows": (n_valid / n_expected)
                        < valid_window_fraction_threshold,
                        "flag_zero_or_negative_minimum": min_value <= 0.0,
                    }
                )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    flag_columns = [column for column in out.columns if column.startswith("flag_")]
    out["n_flags"] = out[flag_columns].sum(axis=1).astype(int)
    out["rank_ascending"] = (
        out.groupby(["station_code", "variable", "duration"])["min_value"]
        .rank(ascending=True, method="min")
        .astype(int)
    )
    return out


# ---------------------------------------------------------------------------
# Rainfall (ETCCDI) indices and diagnostics
# ---------------------------------------------------------------------------

def _longest_run(mask: np.ndarray) -> int:
    longest = current = 0
    for flag in mask:
        current = current + 1 if flag else 0
        longest = max(longest, current)
    return longest


def rainfall_indices(
    daily: pd.DataFrame,
    year_start_month: int = 1,
    wet_day_threshold: float = 1.0,
) -> pd.DataFrame:
    """ETCCDI rainfall indices per station/year (rainfall variable only).

    total, wet/dry days, Rx1day, Rx5day (max 5-day rolling sum), R10/R20/R50,
    SDII, CDD and CWD.  A wet day has rainfall >= ``wet_day_threshold`` mm.
    """
    rainfall = daily[daily["variable"] == "rainfall"]
    rows = []
    for station, _, group in _groups(rainfall):
        completed = _complete_daily_calendar(group)
        if completed.empty:
            continue
        completed = completed.copy()
        completed["analysis_year"] = analysis_year(
            completed["date"], year_start_month
        )
        for year, chunk in completed.groupby("analysis_year"):
            values = chunk["value"]
            observed = values.dropna()
            wet = observed >= wet_day_threshold
            rolling5 = values.rolling(window=5, min_periods=5).sum()
            valid_mask = values.notna().to_numpy()
            dry_mask = (values < wet_day_threshold).fillna(False).to_numpy() & valid_mask
            wet_mask = (values >= wet_day_threshold).fillna(False).to_numpy()
            n_wet = int(wet.sum())
            rows.append(
                {
                    "station_code": station,
                    "analysis_year": int(year),
                    "total_rainfall": float(observed.sum()),
                    "wet_days": n_wet,
                    "dry_days": int((~wet).sum()),
                    "rx1day": float(observed.max()) if len(observed) else np.nan,
                    "rx5day": float(rolling5.max()) if rolling5.notna().any() else np.nan,
                    "r10": int((observed >= 10).sum()),
                    "r20": int((observed >= 20).sum()),
                    "r50": int((observed >= 50).sum()),
                    "sdii": float(observed[wet].sum() / n_wet) if n_wet else np.nan,
                    "cdd": _longest_run(dry_mask),
                    "cwd": _longest_run(wet_mask),
                    "n_days": len(chunk),
                    "n_values": len(observed),
                    "missing_days": len(chunk) - len(observed),
                }
            )
    return pd.DataFrame(rows)


def rainfall_diagnostics(
    daily: pd.DataFrame,
    very_high_threshold: float = 400.0,
    zero_run_length: int = 20,
    repeated_value_min_count: int = 5,
    robust_mad_multiplier: float = 8.0,
    flagged_only: bool = True,
) -> pd.DataFrame:
    """Per-day rainfall plausibility flags (negative, extreme, runs, repeats)."""
    rainfall = daily[daily["variable"] == "rainfall"]
    frames = []
    for station, _, group in _groups(rainfall):
        completed = _complete_daily_calendar(group).copy()
        if completed.empty:
            continue
        values = completed["value"]
        observed = values.dropna()
        median = float(observed.median()) if len(observed) else np.nan
        mad = (
            float((observed - median).abs().median()) * 1.4826
            if len(observed)
            else np.nan
        )
        robust_limit = (
            median + robust_mad_multiplier * mad if np.isfinite(mad) else np.inf
        )
        completed["flag_negative_rainfall"] = (values < 0).fillna(False)
        completed["flag_very_high_rainfall"] = (values >= very_high_threshold).fillna(
            False
        )
        completed["flag_high_robust_outlier"] = (
            (values > robust_limit).fillna(False) if np.isfinite(robust_limit) else False
        )
        zero_mask = (values == 0).fillna(False).to_numpy()
        in_long_zero_run = np.zeros(len(completed), dtype=bool)
        run_start = None
        for index in range(len(zero_mask) + 1):
            if index < len(zero_mask) and zero_mask[index]:
                if run_start is None:
                    run_start = index
            elif run_start is not None:
                if index - run_start >= zero_run_length:
                    in_long_zero_run[run_start:index] = True
                run_start = None
        completed["flag_long_zero_sequence"] = in_long_zero_run
        positive_counts = observed[observed > 0].round(6).value_counts()
        repeated = set(
            positive_counts[positive_counts >= repeated_value_min_count].index
        )
        completed["flag_repeated_positive_value"] = values.round(6).map(
            lambda v: bool(pd.notna(v) and v > 0 and v in repeated)
        )
        completed["station_code"] = station
        frames.append(completed)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    flag_columns = [column for column in out.columns if column.startswith("flag_")]
    out["n_flags"] = out[flag_columns].sum(axis=1).astype(int)
    if flagged_only:
        out = out[out["n_flags"] > 0]
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Measurement / rating diagnostics
# ---------------------------------------------------------------------------

def measurement_diagnostics(
    measurements: pd.DataFrame,
    stage_tolerance: float = 0.0,
    discharge_tolerance: float = 0.0,
    min_group_size: int = 2,
) -> pd.DataFrame:
    """Gauging measurement flags: non-positive values and inconsistent repeats."""
    out = measurements.copy()
    out["flag_stage_non_positive"] = (out["stage_cm"] <= 0).fillna(False)
    out["flag_discharge_non_positive"] = (out["discharge_m3s"] <= 0).fillna(False)
    out["flag_repeated_stage_variable_discharge"] = False
    out["flag_repeated_discharge_variable_stage"] = False
    for _, index in out.groupby(["station_code", "stage_cm"], dropna=True).groups.items():
        if len(index) < min_group_size:
            continue
        spread = out.loc[index, "discharge_m3s"].dropna()
        if len(spread) >= min_group_size and spread.max() - spread.min() > discharge_tolerance:
            out.loc[index, "flag_repeated_stage_variable_discharge"] = True
    for _, index in out.groupby(
        ["station_code", "discharge_m3s"], dropna=True
    ).groups.items():
        if len(index) < min_group_size:
            continue
        spread = out.loc[index, "stage_cm"].dropna()
        if len(spread) >= min_group_size and spread.max() - spread.min() > stage_tolerance:
            out.loc[index, "flag_repeated_discharge_variable_stage"] = True
    flag_columns = [column for column in out.columns if column.startswith("flag_")]
    out["n_flags"] = out[flag_columns].sum(axis=1).astype(int)
    return out


def rating_curve_discharge(
    stage_cm, coefficient_a, coefficient_h0_cm, coefficient_n
) -> float:
    """Power-law rating curve Q = a * (H - h0)^n with H and h0 in cm."""
    if any(
        value is None or (isinstance(value, float) and np.isnan(value))
        for value in (stage_cm, coefficient_a, coefficient_h0_cm, coefficient_n)
    ):
        return float("nan")
    base = float(stage_cm) - float(coefficient_h0_cm)
    if base <= 0:
        return float("nan")
    return float(coefficient_a) * base ** float(coefficient_n)


def rating_diagnostics(
    rating_curves: pd.DataFrame,
    measurements: pd.DataFrame,
    envelope_quantile: float = 0.95,
) -> pd.DataFrame:
    """Compare gauged discharges with the rating-curve prediction.

    Each measurement is matched to a segment valid for its date and stage
    range; predicted discharge, relative error and log residual are computed,
    and residuals outside the empirical |log residual| envelope are flagged.
    """
    rows = []
    for _, measurement in measurements.iterrows():
        stage = measurement.get("stage_cm")
        observed = measurement.get("discharge_m3s")
        measurement_date = measurement.get("measurement_date") or measurement.get(
            "measurement_datetime"
        )
        candidates = rating_curves[
            rating_curves["station_code"] == measurement.get("station_code")
        ]

        def in_validity(row) -> bool:
            valid_from, valid_to = row.get("valid_from"), row.get("valid_to")
            if measurement_date is None or pd.isna(measurement_date):
                return True
            timestamp = pd.Timestamp(measurement_date)
            if valid_from is not None and pd.notna(valid_from) and timestamp < pd.Timestamp(valid_from):
                return False
            if valid_to is not None and pd.notna(valid_to) and timestamp > pd.Timestamp(valid_to):
                return False
            return True

        def in_stage_range(row) -> bool:
            if stage is None or pd.isna(stage):
                return False
            low, high = row.get("stage_min_cm"), row.get("stage_max_cm")
            if low is not None and pd.notna(low) and stage < low:
                return False
            if high is not None and pd.notna(high) and stage > high:
                return False
            return True

        matches = candidates[
            candidates.apply(lambda row: in_validity(row) and in_stage_range(row), axis=1)
        ]
        row = {
            "station_code": measurement.get("station_code"),
            "measurement_date": measurement_date,
            "stage_cm": stage,
            "observed_discharge_m3s": observed,
            "predicted_discharge_m3s": np.nan,
            "relative_error_pct": np.nan,
            "log_residual": np.nan,
            "flag_no_valid_curve": matches.empty,
            "flag_non_positive_measurement": bool(
                pd.isna(observed) or observed <= 0
            ),
        }
        if not matches.empty:
            segment = matches.iloc[0]
            predicted = rating_curve_discharge(
                stage,
                segment.get("coefficient_a"),
                segment.get("coefficient_h0_cm"),
                segment.get("coefficient_n"),
            )
            row["predicted_discharge_m3s"] = predicted
            if (
                pd.notna(predicted)
                and predicted > 0
                and pd.notna(observed)
                and observed > 0
            ):
                row["relative_error_pct"] = 100.0 * (observed - predicted) / observed
                row["log_residual"] = float(np.log(observed) - np.log(predicted))
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    residuals = out["log_residual"].abs().dropna()
    envelope = (
        _quantile(residuals.to_numpy(dtype=float), envelope_quantile, "linear")
        if len(residuals)
        else np.nan
    )
    out["flag_outside_residual_envelope"] = out["log_residual"].abs() > envelope
    out["flag_large_relative_error_10pct"] = out["relative_error_pct"].abs() > 10
    out["flag_large_relative_error_25pct"] = out["relative_error_pct"].abs() > 25
    flag_columns = [column for column in out.columns if column.startswith("flag_")]
    out["n_flags"] = out[flag_columns].fillna(False).sum(axis=1).astype(int)
    return out


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def analyze_hydro_data(
    data,
    analysis: str,
    variable: Optional[str] = None,
    station_code=None,
    period: str = "annual",
    year_start_month: int = 1,
    durations: Sequence[int] = (1, 3, 7, 15, 30),
    wet_day_threshold: float = 1.0,
    exceedance_probabilities: Sequence[int] = tuple(range(1, 100)),
    complete_years_only: bool = True,
    **kwargs,
):
    """Source-neutral analysis dispatcher (mirrors hydroDataBR's).

    ``analysis`` is one of: ``daily_statistics``, ``daily_availability``,
    ``flow_duration``, ``flow_indices``, ``monthly_flow_indices``,
    ``rainfall_indices``, ``annual_maxima``, ``rainfall_annual_maxima``,
    ``low_flows``, ``daily_gap_summary``, ``rainfall_diagnostics``.
    """
    name = str(analysis).strip().lower().replace("-", "_")
    if name not in ANALYSES:
        raise ValueError(
            f"Unknown analysis {analysis!r}. Valid analyses: {', '.join(ANALYSES)}."
        )
    daily = extract_daily_data(data)
    daily = prefer_daily_rows(daily)
    if station_code is not None:
        codes = (
            [str(code) for code in station_code]
            if isinstance(station_code, (list, tuple, set))
            else [str(station_code)]
        )
        daily = daily[daily["station_code"].isin(codes)]
    if variable is not None:
        if variable not in DAILY_VARIABLES:
            raise ValueError(f"variable must be one of {DAILY_VARIABLES}.")
        daily = daily[daily["variable"] == variable]

    if name == "daily_statistics":
        return daily_statistics(daily, period=period)
    if name == "daily_availability":
        return daily_availability(daily, period=period)
    if name == "flow_duration":
        return flow_duration(daily, exceedance_probabilities)
    if name == "flow_indices":
        return flow_indices(daily)
    if name == "monthly_flow_indices":
        return monthly_flow_indices(daily)
    if name == "rainfall_indices":
        return rainfall_indices(daily, year_start_month, wet_day_threshold)
    if name == "annual_maxima":
        return annual_maxima(
            daily, year_start_month, complete_years_only, **kwargs
        )
    if name == "rainfall_annual_maxima":
        return annual_maxima(
            daily[daily["variable"] == "rainfall"],
            year_start_month,
            complete_years_only,
            **kwargs,
        )
    if name == "low_flows":
        return low_flows(daily, year_start_month, durations, **kwargs)
    if name == "daily_gap_summary":
        return daily_gap_summary(daily, period=period)
    if name == "rainfall_diagnostics":
        return rainfall_diagnostics(daily, **kwargs)
    raise AssertionError("unreachable")
