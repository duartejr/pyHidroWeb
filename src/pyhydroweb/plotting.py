"""Plotting dispatcher: matplotlib translations of hydroDataBR's ggplot2 layer.

Python translation of the plot surface of hydroDataBR (hydrostat/hydroDataBR,
MIT).  Every plot function returns a :class:`matplotlib.figure.Figure`.
matplotlib is an optional dependency (``pip install pyhydroweb[plot]``).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .exceptions import MissingDependencyError

PLOTS = (
    "daily_series",
    "daily_availability",
    "monthly_summary",
    "annual_summary",
    "flow_duration",
    "rating_curves",
    "measurements",
    "annual_maxima",
    "low_flows",
    "rainfall_indices",
    "cross_section_profile",
    "cross_section_overlay",
)

_VARIABLE_LABELS = {
    "discharge": "Vazão (m³/s)",
    "stage": "Cota (cm)",
    "rainfall": "Chuva (mm)",
}


def _pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg", force=False)
        import matplotlib.pyplot as plt

        return plt
    except ImportError:
        raise MissingDependencyError(
            "Plotting requires matplotlib (pip install pyhydroweb[plot])."
        ) from None


def plot_hydro_data(
    data,
    plot: str,
    variable: Optional[str] = None,
    station_code=None,
    **kwargs,
):
    """Source-neutral plotting dispatcher (mirrors hydroDataBR's).

    ``plot`` is one of: ``daily_series``, ``daily_availability``,
    ``monthly_summary``, ``annual_summary``, ``flow_duration``,
    ``rating_curves``, ``measurements``, ``annual_maxima``, ``low_flows``,
    ``rainfall_indices``, ``cross_section_profile``, ``cross_section_overlay``.
    """
    name = str(plot).strip().lower().replace("-", "_")
    if name not in PLOTS:
        raise ValueError(f"Unknown plot {plot!r}. Valid plots: {', '.join(PLOTS)}.")
    if name == "daily_series":
        return plot_daily_series(data, variable=variable, station_code=station_code, **kwargs)
    if name == "daily_availability":
        return plot_daily_availability(data, variable=variable, station_code=station_code, **kwargs)
    if name == "monthly_summary":
        return plot_monthly_summary(data, variable=variable, station_code=station_code, **kwargs)
    if name == "annual_summary":
        return plot_annual_summary(data, variable=variable, station_code=station_code, **kwargs)
    if name == "flow_duration":
        return plot_flow_duration_curve(data, station_code=station_code, **kwargs)
    if name == "rating_curves":
        return plot_rating_curves(data, station_code=station_code, **kwargs)
    if name == "measurements":
        return plot_discharge_measurements(data, station_code=station_code, **kwargs)
    if name == "annual_maxima":
        return plot_annual_maxima(data, station_code=station_code, **kwargs)
    if name == "low_flows":
        return plot_low_flows(data, station_code=station_code, **kwargs)
    if name == "rainfall_indices":
        return plot_rainfall_indices(data, station_code=station_code, **kwargs)
    if name in {"cross_section_profile", "cross_section_overlay"}:
        return plot_cross_sections(
            data,
            plot_type="profile" if name.endswith("profile") else "overlay",
            station_code=station_code,
            **kwargs,
        )
    raise AssertionError("unreachable")


def _filter_daily(data, variable, station_code) -> pd.DataFrame:
    from .analysis import extract_daily_data

    daily = extract_daily_data(data)
    if variable is not None:
        daily = daily[daily["variable"] == variable]
    if station_code is not None:
        daily = daily[daily["station_code"].astype(str) == str(station_code)]
    return daily


def plot_daily_series(data, variable=None, station_code=None, title=None):
    """Daily time series: lines for discharge/stage, bars for rainfall."""
    plt = _pyplot()
    daily = _filter_daily(data, variable, station_code)
    variables = sorted(daily["variable"].dropna().unique())
    fig, axes = plt.subplots(
        len(variables) or 1, 1, figsize=(10, 3 * (len(variables) or 1)), squeeze=False
    )
    for axis, name in zip(axes.ravel(), variables or ["(empty)"]):
        subset = daily[daily["variable"] == name].sort_values("date")
        for station, group in subset.groupby("station_code"):
            if name == "rainfall":
                axis.bar(group["date"], group["value"], width=1.0, label=str(station))
            else:
                axis.plot(group["date"], group["value"], label=str(station))
        axis.set_ylabel(_VARIABLE_LABELS.get(name, name))
        axis.set_xlabel("Data")
        if subset["station_code"].nunique() > 1:
            axis.legend(fontsize=8)
    fig.suptitle(title or "Série diária")
    fig.tight_layout()
    return fig


def plot_daily_availability(data, variable=None, station_code=None, title=None):
    """Monthly availability heatmap (x = year, y = month, color = missing %)."""
    from .analysis import daily_availability

    plt = _pyplot()
    daily = _filter_daily(data, variable, station_code)
    table = daily_availability(daily, period="monthly")
    fig, ax = plt.subplots(figsize=(10, 4))
    if table.empty:
        ax.set_title("Sem dados")
        return fig
    table = table.copy()
    table["year"] = table["period"].str.slice(0, 4).astype(int)
    table["month"] = table["period"].str.slice(5, 7).astype(int)
    pivot = table.pivot_table(
        index="month", columns="year", values="missing_pct", aggfunc="mean"
    )
    mesh = ax.pcolormesh(
        pivot.columns, pivot.index, pivot.to_numpy(), cmap="RdYlBu_r", vmin=0, vmax=100
    )
    fig.colorbar(mesh, ax=ax, label="Falhas (%)")
    ax.set_xlabel("Ano")
    ax.set_ylabel("Mês")
    ax.set_title(title or "Disponibilidade mensal")
    fig.tight_layout()
    return fig


def plot_monthly_summary(data, variable=None, station_code=None, statistic="mean_value", title=None):
    """Climatological monthly regime of a chosen statistic."""
    from .analysis import daily_statistics

    plt = _pyplot()
    daily = _filter_daily(data, variable, station_code)
    table = daily_statistics(daily, period="monthly")
    fig, ax = plt.subplots(figsize=(8, 4))
    if table.empty:
        ax.set_title("Sem dados")
        return fig
    table = table.copy()
    table["month"] = table["period"].str.slice(5, 7).astype(int)
    regime = table.groupby(["variable", "month"])[statistic].mean().reset_index()
    for name, group in regime.groupby("variable"):
        if name == "rainfall":
            ax.bar(group["month"], group[statistic], label=_VARIABLE_LABELS.get(name, name))
        else:
            ax.plot(group["month"], group[statistic], marker="o", label=_VARIABLE_LABELS.get(name, name))
    ax.set_xticks(range(1, 13))
    ax.set_xlabel("Mês")
    ax.set_ylabel(statistic)
    ax.legend(fontsize=8)
    ax.set_title(title or "Regime mensal")
    fig.tight_layout()
    return fig


def plot_annual_summary(data, variable=None, station_code=None, statistic="mean_value", title=None):
    """Annual series of a chosen statistic."""
    from .analysis import daily_statistics

    plt = _pyplot()
    daily = _filter_daily(data, variable, station_code)
    table = daily_statistics(daily, period="annual")
    fig, ax = plt.subplots(figsize=(8, 4))
    if table.empty:
        ax.set_title("Sem dados")
        return fig
    table = table.copy()
    table["year"] = table["period"].astype(int)
    for name, group in table.groupby("variable"):
        ax.plot(group["year"], group[statistic], marker="o", label=_VARIABLE_LABELS.get(name, name))
    ax.set_xlabel("Ano")
    ax.set_ylabel(statistic)
    ax.legend(fontsize=8)
    ax.set_title(title or "Resumo anual")
    fig.tight_layout()
    return fig


def _norm_ppf(p: np.ndarray) -> np.ndarray:
    """Inverse standard-normal CDF (Acklam's rational approximation).

    Avoids a scipy dependency; max abs error ~1.15e-9, ample for plot axes.
    """
    a = (
        -3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
        1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
        6.680131188771972e01, -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
        -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
        3.754408661907416e00,
    )
    p = np.asarray(p, dtype=float)
    out = np.full_like(p, np.nan)
    low, high = 0.02425, 1 - 0.02425
    mask = (p > 0) & (p < low)
    if mask.any():
        q = np.sqrt(-2 * np.log(p[mask]))
        out[mask] = (
            ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
        ) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    mask = (p >= low) & (p <= high)
    if mask.any():
        q = p[mask] - 0.5
        r = q * q
        out[mask] = (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        ) / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    mask = (p > high) & (p < 1)
    if mask.any():
        q = np.sqrt(-2 * np.log(1 - p[mask]))
        out[mask] = -(
            ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
        ) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    return out


def plot_flow_duration_curve(
    data, station_code=None, log_y: bool = True, title=None
):
    """Flow-duration curve on a normal-probability x-axis (qnorm transform)."""
    from .analysis import extract_daily_data, flow_duration

    plt = _pyplot()
    if isinstance(data, pd.DataFrame) and "permanence_pct" in data.columns:
        fdc = data
    else:
        daily = extract_daily_data(data)
        if station_code is not None:
            daily = daily[daily["station_code"].astype(str) == str(station_code)]
        fdc = flow_duration(daily)
    fig, ax = plt.subplots(figsize=(8, 5))
    if fdc.empty:
        ax.set_title("Sem dados")
        return fig
    for (station, variable), group in fdc.groupby(["station_code", "variable"]):
        probabilities = group["permanence_pct"].to_numpy(dtype=float) / 100.0
        ax.plot(
            _norm_ppf(probabilities),
            group["value"],
            marker=".",
            label=f"{station} ({variable})",
        )
    ticks = np.array([1, 5, 10, 30, 50, 70, 90, 95, 99]) / 100.0
    ax.set_xticks(_norm_ppf(ticks))
    ax.set_xticklabels([f"{int(t * 100)}" for t in ticks])
    if log_y:
        ax.set_yscale("log")
    ax.set_xlabel("Permanência (%)")
    ax.set_ylabel("Vazão (m³/s)")
    ax.legend(fontsize=8)
    ax.set_title(title or "Curva de permanência")
    fig.tight_layout()
    return fig


def plot_rating_curves(
    rating_curves: pd.DataFrame,
    measurements: Optional[pd.DataFrame] = None,
    station_code=None,
    n_points: int = 80,
    title=None,
):
    """Rating curves Q = a*(H-h0)^n, optionally overlaid with measurements."""
    from .analysis import rating_curve_discharge

    plt = _pyplot()
    curves = rating_curves
    if station_code is not None:
        curves = curves[curves["station_code"].astype(str) == str(station_code)]
    fig, ax = plt.subplots(figsize=(8, 5))
    for _, segment in curves.iterrows():
        low = segment.get("stage_min_cm")
        high = segment.get("stage_max_cm")
        if pd.isna(low) or pd.isna(high) or high <= low:
            continue
        stages = np.linspace(low, high, n_points)
        discharges = [
            rating_curve_discharge(
                stage,
                segment.get("coefficient_a"),
                segment.get("coefficient_h0_cm"),
                segment.get("coefficient_n"),
            )
            for stage in stages
        ]
        ax.plot(discharges, stages, label=str(segment.get("rating_curve_segment_id")))
    if measurements is not None and not measurements.empty:
        subset = measurements
        if station_code is not None:
            subset = subset[subset["station_code"].astype(str) == str(station_code)]
        ax.scatter(
            subset["discharge_m3s"], subset["stage_cm"], s=12, alpha=0.6, color="black"
        )
    ax.set_xlabel("Vazão (m³/s)")
    ax.set_ylabel("Cota (cm)")
    if len(curves) <= 12:
        ax.legend(fontsize=7)
    ax.set_title(title or "Curvas-chave")
    fig.tight_layout()
    return fig


def plot_discharge_measurements(
    measurements: pd.DataFrame, station_code=None, plot_type: str = "rating", title=None
):
    """Gauging scatter: ``rating`` (Q vs stage), ``year`` or ``velocity``."""
    plt = _pyplot()
    subset = measurements
    if station_code is not None:
        subset = subset[subset["station_code"].astype(str) == str(station_code)]
    fig, ax = plt.subplots(figsize=(8, 5))
    if plot_type == "rating":
        ax.scatter(subset["discharge_m3s"], subset["stage_cm"], s=12, alpha=0.6)
        ax.set_xlabel("Vazão (m³/s)")
        ax.set_ylabel("Cota (cm)")
    elif plot_type == "year":
        years = pd.to_datetime(subset["measurement_datetime"], errors="coerce").dt.year
        counts = years.value_counts().sort_index()
        ax.bar(counts.index, counts.values)
        ax.set_xlabel("Ano")
        ax.set_ylabel("Nº de medições")
    elif plot_type == "velocity":
        ax.scatter(subset["mean_velocity_ms"], subset["stage_cm"], s=12, alpha=0.6)
        ax.set_xlabel("Velocidade média (m/s)")
        ax.set_ylabel("Cota (cm)")
    else:
        raise ValueError("plot_type must be 'rating', 'year' or 'velocity'.")
    ax.set_title(title or "Medições de descarga")
    fig.tight_layout()
    return fig


def plot_annual_maxima(data, station_code=None, title=None):
    """Annual-maxima lollipop plot colored by flag count."""
    from .analysis import analyze_hydro_data

    plt = _pyplot()
    table = (
        data
        if isinstance(data, pd.DataFrame) and "max_value" in getattr(data, "columns", [])
        else analyze_hydro_data(data, "annual_maxima", station_code=station_code)
    )
    fig, ax = plt.subplots(figsize=(9, 4))
    if table.empty:
        ax.set_title("Sem dados")
        return fig
    colors = table["n_flags"].map(lambda n: "tab:red" if n else "tab:blue")
    ax.vlines(table["analysis_year"], 0, table["max_value"], color=colors, alpha=0.6)
    ax.scatter(table["analysis_year"], table["max_value"], color=colors, zorder=3)
    ax.set_xlabel("Ano")
    ax.set_ylabel("Máxima anual")
    ax.set_title(title or "Máximas anuais (vermelho = com flags)")
    fig.tight_layout()
    return fig


def plot_low_flows(data, station_code=None, title=None):
    """Annual minima of the moving averages, one line per duration."""
    from .analysis import analyze_hydro_data

    plt = _pyplot()
    table = (
        data
        if isinstance(data, pd.DataFrame) and "duration" in getattr(data, "columns", [])
        else analyze_hydro_data(data, "low_flows", station_code=station_code)
    )
    fig, ax = plt.subplots(figsize=(9, 4))
    if table.empty:
        ax.set_title("Sem dados")
        return fig
    for duration, group in table.groupby("duration"):
        ax.plot(
            group["analysis_year"], group["min_value"], marker="o", label=f"Q{duration}"
        )
    ax.set_xlabel("Ano")
    ax.set_ylabel("Mínima anual (m³/s)")
    ax.legend(fontsize=8)
    ax.set_title(title or "Mínimas móveis anuais")
    fig.tight_layout()
    return fig


def plot_rainfall_indices(data, station_code=None, indices=("rx1day", "rx5day", "sdii"), title=None):
    """ETCCDI index panels over the years."""
    from .analysis import analyze_hydro_data

    plt = _pyplot()
    table = (
        data
        if isinstance(data, pd.DataFrame) and "rx1day" in getattr(data, "columns", [])
        else analyze_hydro_data(data, "rainfall_indices", station_code=station_code)
    )
    fig, axes = plt.subplots(len(indices), 1, figsize=(9, 2.6 * len(indices)), squeeze=False)
    if table.empty:
        axes[0][0].set_title("Sem dados")
        return fig
    for axis, index_name in zip(axes.ravel(), indices):
        for station, group in table.groupby("station_code"):
            axis.plot(group["analysis_year"], group[index_name], marker="o", label=str(station))
        axis.set_ylabel(index_name)
    axes.ravel()[-1].set_xlabel("Ano")
    fig.suptitle(title or "Índices de chuva (ETCCDI)")
    fig.tight_layout()
    return fig


def plot_cross_sections(
    cross_sections,
    plot_type: str = "profile",
    station_code=None,
    section_id=None,
    title=None,
):
    """Cross-section profile (one section) or overlay (all sections greyed)."""
    from .cross_sections import (
        prepare_cross_section_vertices,
        section_summary_from_vertices,
        select_cross_section_id,
    )

    plt = _pyplot()
    vertices = prepare_cross_section_vertices(cross_sections, station_code)
    fig, ax = plt.subplots(figsize=(8, 5))
    if vertices.empty:
        ax.set_title("Sem dados")
        return fig
    if plot_type == "profile":
        sections = section_summary_from_vertices(vertices)
        selected = select_cross_section_id(sections, section_id or "latest")
        profile = vertices[vertices["cross_section_id"] == selected]
        ax.plot(profile["vertex_distance_m"], profile["vertex_stage_cm"], marker=".")
        ax.set_title(title or f"Perfil transversal — {selected}")
    elif plot_type == "overlay":
        for section, group in vertices.groupby("cross_section_id"):
            ax.plot(
                group["vertex_distance_m"],
                group["vertex_stage_cm"],
                color="grey",
                alpha=0.4,
            )
        ax.set_title(title or "Perfis transversais (sobrepostos)")
    else:
        raise ValueError("plot_type must be 'profile' or 'overlay'.")
    ax.set_xlabel("Distância horizontal (m)")
    ax.set_ylabel("Cota (cm)")
    fig.tight_layout()
    return fig
