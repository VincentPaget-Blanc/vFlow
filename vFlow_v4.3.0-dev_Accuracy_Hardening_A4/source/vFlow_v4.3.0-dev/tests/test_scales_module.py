import pytest


def test_flow_scales_register_when_matplotlib_is_available():
    pytest.importorskip("matplotlib")

    from matplotlib import scale as mscale

    from vflow.core.scales import _flow_fmt, register_flow_scales

    register_flow_scales()

    assert mscale.scale_factory("asinh", None).__class__.name == "asinh"
    assert _flow_fmt(-10_000_000, None) == "-10⁷"

