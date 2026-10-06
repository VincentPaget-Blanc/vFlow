from vflow.config.constants import (
    ALL_SCALES,
    _LINESTYLE_MAP,
    _N_FILE_COLORS,
    _N_REGION_COLORS,
    FILE_COLORS,
    REGION_COLORS,
)
from vflow.config.themes import THEMES


def test_theme_defaults_are_available():
    assert THEMES["dark"]["sidebar_bg"] == "#2b2b2b"
    assert THEMES["light"]["plot_bg"] == "#ffffff"


def test_shared_constants_expose_explicit_a2_transform_identities():
    assert ALL_SCALES == [
        "linear", "log", "asinh", "logicle_gml2",
        "legacy_biexp", "legacy_logicle",
    ]
    assert _LINESTYLE_MAP["─── Solid"] == "-"
    assert _LINESTYLE_MAP["··· Dotted"] == ":"
    assert _N_FILE_COLORS == len(FILE_COLORS)
    assert _N_REGION_COLORS == len(REGION_COLORS)

