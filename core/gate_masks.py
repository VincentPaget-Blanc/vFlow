"""Gate mask computation for vFlow gate dictionaries."""

from __future__ import annotations

import numpy as np

from vflow.config.constants import (
    GATE_PALETTE,
    REGION_COLORS,
    _N_REGION_COLORS,
)
from .gates import active_x_boundaries, active_y_boundary, active_y_boundaries
from .transforms import forward_transform


def fluorophore_label(channel: str) -> str:
    if not channel:
        return channel
    parts = channel.rsplit("_", 1)
    return parts[-1] if parts[-1] else channel


def region_masks(
    xa,
    ya,
    x_boundaries,
    y_boundary,
    *,
    y_boundaries=None,
    x_channel: str = "X",
    y_channel: str = "Y",
):
    """Compute crosshair region masks and colors."""
    if not isinstance(xa, np.ndarray) or xa.dtype != np.float64:
        xa = np.asarray(xa, float)
    if not isinstance(ya, np.ndarray) or ya.dtype != np.float64:
        ya = np.asarray(ya, float)
    xbs = sorted(x_boundaries) if x_boundaries else []

    if y_boundaries is not None and len(y_boundaries) > 0:
        ybs = sorted(float(v) for v in y_boundaries)
    elif y_boundary is not None:
        ybs = [float(y_boundary)]
    else:
        ybs = []

    n_x = len(xbs)
    n_y = len(ybs)
    has_x = n_x > 0
    has_y = n_y > 0

    xf = fluorophore_label(x_channel or "X")
    yf = fluorophore_label(y_channel or "Y")

    if not has_x and not has_y:
        return {}, []

    if n_x == 0:
        x_band_labels = []
    elif n_x == 1:
        x_band_labels = [f"{xf}-", f"{xf}+"]
    elif n_x == 2:
        x_band_labels = [f"{xf}-", f"{xf}(m)", f"{xf}+"]
    else:
        mid = [f"{xf}(m{i})" for i in range(1, n_x)]
        x_band_labels = [f"{xf}-"] + mid + [f"{xf}+"]

    if n_y == 0:
        y_band_labels = []
    elif n_y == 1:
        y_band_labels = [f"{yf}-", f"{yf}+"]
    elif n_y == 2:
        y_band_labels = [f"{yf}-", f"{yf}(m)", f"{yf}+"]
    else:
        mid = [f"{yf}(m{i})" for i in range(1, n_y)]
        y_band_labels = [f"{yf}-"] + mid + [f"{yf}+"]

    if has_x:
        x_edges = [-np.inf] + xbs + [np.inf]
        x_masks = [
            (xa > x_edges[i]) & (xa <= x_edges[i + 1])
            for i in range(len(x_edges) - 1)
        ]
    else:
        x_masks = [np.ones(len(xa), bool)]
        x_band_labels = ["All"]

    if has_y:
        y_edges = [-np.inf] + ybs + [np.inf]
        y_masks = [
            (ya > y_edges[i]) & (ya <= y_edges[i + 1])
            for i in range(len(y_edges) - 1)
        ]
    else:
        y_masks = [np.ones(len(ya), bool)]
        y_band_labels = ["All"]

    if not has_x:
        regions = {}
        colors = []
        for i, (ylbl, ym) in enumerate(zip(reversed(y_band_labels), reversed(y_masks))):
            regions[ylbl] = ym
            colors.append(REGION_COLORS[i % _N_REGION_COLORS])
        return regions, colors

    if not has_y:
        regions = {}
        colors = []
        for i, (xlbl, xm) in enumerate(zip(x_band_labels, x_masks)):
            regions[xlbl] = xm
            colors.append(REGION_COLORS[i % _N_REGION_COLORS])
        return regions, colors

    regions = {}
    colors = []
    ci = 0
    for yi in range(len(y_band_labels) - 1, -1, -1):
        ylbl = y_band_labels[yi]
        ym = y_masks[yi]
        for xlbl, xm in zip(x_band_labels, x_masks):
            regions[f"{ylbl}/{xlbl}"] = xm & ym
            colors.append(REGION_COLORS[ci % _N_REGION_COLORS])
            ci += 1
    return regions, colors


def compute_gate_regions(
    gate: dict,
    x,
    y,
    *,
    x_scale: str,
    y_scale: str,
    cofactor: float,
    x_channel: str = "X",
    y_channel: str = "Y",
):
    """Compute gate region masks and colors without app/cache state."""
    if not gate or not gate.get("applied"):
        return {}, []

    if not isinstance(x, np.ndarray) or x.dtype != np.float64:
        xa = np.asarray(x, float)
    else:
        xa = x
    if not isinstance(y, np.ndarray) or y.dtype != np.float64:
        ya = np.asarray(y, float)
    else:
        ya = y

    gt = gate.get("type", "crosshair")
    c = gate.get("color", GATE_PALETTE[0])

    if gt == "crosshair":
        xbs = active_x_boundaries(gate)
        yb = active_y_boundary(gate)
        ybs = gate.get("y_boundaries")
        if ybs:
            return region_masks(
                xa,
                ya,
                xbs,
                None,
                y_boundaries=active_y_boundaries(gate),
                x_channel=x_channel,
                y_channel=y_channel,
            )
        return region_masks(
            xa,
            ya,
            xbs,
            yb,
            x_channel=x_channel,
            y_channel=y_channel,
        )

    if gt == "rectangle":
        xlo = min(gate["x0"], gate["x1"])
        xhi = max(gate["x0"], gate["x1"])
        ylo = min(gate["y0"], gate["y1"])
        yhi = max(gate["y0"], gate["y1"])
        mask = (xa >= xlo) & (xa <= xhi) & (ya >= ylo) & (ya <= yhi)
        return {"IN": mask, "OUT": ~mask}, [c, REGION_COLORS[1]]

    if gt == "ellipse":
        cx = (gate["x0"] + gate["x1"]) / 2.0
        cy = (gate["y0"] + gate["y1"]) / 2.0
        a = abs(gate["x1"] - gate["x0"]) / 2.0
        b = abs(gate["y1"] - gate["y0"]) / 2.0
        if a < 1e-12 or b < 1e-12:
            return {}, []
        fin = np.isfinite(xa) & np.isfinite(ya)
        mask = np.zeros(len(xa), bool)
        mask[fin] = (((xa[fin] - cx) ** 2 / a**2 + (ya[fin] - cy) ** 2 / b**2) <= 1.0)
        return {"IN": mask, "OUT": ~mask}, [c, REGION_COLORS[1]]

    if gt == "polygon":
        from matplotlib.path import Path as MplPath

        verts = gate.get("vertices", [])
        if len(verts) < 3:
            return {}, []

        vx_t = forward_transform(
            np.array([v[0] for v in verts], dtype=np.float64), x_scale, cofactor
        )
        vy_t = forward_transform(
            np.array([v[1] for v in verts], dtype=np.float64), y_scale, cofactor
        )
        valid_verts = [
            (float(tx), float(ty))
            for tx, ty in zip(vx_t, vy_t)
            if np.isfinite(tx) and np.isfinite(ty)
        ]
        if len(valid_verts) < 3:
            return {}, []

        mpl_path = MplPath(valid_verts + [valid_verts[0]])

        fin = np.isfinite(xa) & np.isfinite(ya)
        mask = np.zeros(len(xa), bool)
        if fin.any():
            xa_t = forward_transform(xa[fin], x_scale, cofactor)
            ya_t = forward_transform(ya[fin], y_scale, cofactor)
            fin2 = np.isfinite(xa_t) & np.isfinite(ya_t)
            if fin2.any():
                staging = np.zeros(int(fin.sum()), bool)
                staging[fin2] = mpl_path.contains_points(
                    np.column_stack([xa_t[fin2], ya_t[fin2]])
                )
                mask[fin] = staging

        return {"IN": mask, "OUT": ~mask}, [c, REGION_COLORS[1]]

    return {}, []
