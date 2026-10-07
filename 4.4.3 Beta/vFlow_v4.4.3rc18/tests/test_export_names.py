from vflow.services.export_names import (
    active_export_stem,
    export_channel_token,
    xy_export_prefix,
)


def test_export_channel_token_uses_fallback_and_replaces_spaces():
    assert export_channel_token(None, "X") == "X"
    assert export_channel_token("Area Channel", "X") == "Area_Channel"


def test_active_export_stem_uses_first_active_path():
    assert active_export_stem({"/tmp/sample one.csv": object()}) == "sample one"
    assert active_export_stem({}) == "flowjo_export"


def test_xy_export_prefix_matches_legacy_pattern():
    active = {"/tmp/sample.csv": object()}

    assert xy_export_prefix(active, "FSC A", "SSC A") == "sample_FSC_A_vs_SSC_A"
