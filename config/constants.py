"""Shared constants for vFlow."""

ALL_SCALES = ["linear", "log", "biexp", "asinh", "logicle"]

_LOCK_SNAP: list = sorted(
    {
        0,
        *[s * 10**e for e in range(1, 8) for s in (1, 2, 5)],
        *[-s * 10**e for e in range(1, 8) for s in (1, 2, 5)],
    }
)

_FLOW_MINOR_TICKS: list = sorted(
    {
        m * 10 ** (e - 1)
        for e in range(2, 8)
        for m in range(2, 10)
    }
    | {
        -m * 10 ** (e - 1)
        for e in range(2, 8)
        for m in range(2, 10)
    }
)

GATE_PALETTE = [
    "#ff6b6b",
    "#ffd93d",
    "#6bcb77",
    "#4d96ff",
    "#ff9a3c",
    "#c77dff",
    "#ff6bcd",
    "#4ecdc4",
]
HANDLE_PX = 12
HANDLE_SZ = 70

FILE_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]
_N_FILE_COLORS = len(FILE_COLORS)

REGION_COLORS = [
    "#e41a1c",
    "#377eb8",
    "#4daf4a",
    "#ff7f00",
    "#984ea3",
    "#a65628",
    "#f781bf",
    "#aaaaaa",
    "#66c2a5",
    "#fc8d62",
    "#8da0cb",
    "#e78ac3",
    "#a6d854",
    "#ffd92f",
    "#e5c494",
    "#b3b3b3",
]
_N_REGION_COLORS = len(REGION_COLORS)

_LINESTYLE_MAP = {"─── Solid": "-", "- - Dashed": "--", "··· Dotted": ":"}
_LINESTYLE_INV = {v: k for k, v in _LINESTYLE_MAP.items()}

KDE_SUBSAMPLE = 30_000
RENDER_CAP = 10_000
_GMC_MAX = 400
