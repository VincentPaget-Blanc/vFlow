"""Batch plot statistics export helpers."""

from __future__ import annotations

import numpy as np


def safe_population_column_name(region_name: str) -> str:
    """Return the legacy-safe population column suffix for a region."""
    return region_name.replace("/", "_").replace(" ", "_")


def format_display_number(value: float) -> str:
    """Format values for the batch plot stats sidebar."""
    if not np.isfinite(value):
        return "\u2014"
    if abs(value) >= 1e6:
        return f"{value:.3e}"
    if abs(value) >= 100:
        return f"{value:,.1f}"
    return f"{value:.3f}"


def short_display_label(label: str, *, max_chars: int = 25) -> str:
    """Return the legacy shortened tree label."""
    return label[: max_chars - 1] + "\u2026" if len(label) > max_chars else label


def distribution_summary(values) -> dict:
    """Return n, median, mean, and IQR for display in the stats sidebar."""
    vals = np.asarray(values)
    n = len(vals)
    if n == 0:
        return {
            "n": 0,
            "median": float("nan"),
            "mean": float("nan"),
            "iqr": float("nan"),
        }
    q25, q75 = np.percentile(vals, [25, 75])
    return {
        "n": n,
        "median": float(np.median(vals)),
        "mean": float(np.mean(vals)),
        "iqr": float(q75 - q25),
    }


def build_batch_plot_stats_row(
    *,
    sample_label: str,
    values,
    populations: dict,
    population_sems: dict | None = None,
    column: str,
    gate: str,
    region: str,
) -> dict:
    """Build one legacy batch-plot statistics export row."""
    vals = np.asarray(values)
    n = len(vals)
    if n:
        p5, q25, q75, p95 = np.percentile(vals, [5, 25, 75, 95])
    row = {
        "Sample": sample_label,
        "Col": column,
        "Gate": gate,
        "Region": region,
        "N": n,
        "Mean": round(float(np.mean(vals)), 4) if n else "",
        "Median": round(float(np.median(vals)), 4) if n else "",
        "Std": round(float(np.std(vals, ddof=1)), 4) if n > 1 else "",
        "IQR": round(float(q75 - q25), 4) if n else "",
        "p5": round(float(p5), 4) if n else "",
        "p95": round(float(p95), 4) if n else "",
    }
    population_sems = population_sems or {}
    safe_names = {}
    for region_name in populations:
        safe = safe_population_column_name(region_name)
        prior = safe_names.get(safe)
        if prior is not None and prior != region_name:
            raise ValueError(
                "Batch Plot population names collide after CSV-column normalization: "
                f"{prior!r} and {region_name!r} both become {safe!r}."
            )
        safe_names[safe] = region_name

    for region_name, pct in populations.items():
        safe = safe_population_column_name(region_name)
        row[f"Pop_{safe}_pct"] = round(pct, 3)
        if region_name in population_sems:
            row[f"Pop_{safe}_counting_SE_pct"] = round(
                float(population_sems[region_name]), 6
            )
    return row
