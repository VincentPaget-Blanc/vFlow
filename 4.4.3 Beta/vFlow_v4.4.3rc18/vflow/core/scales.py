"""Custom Matplotlib scales used by vFlow."""

from __future__ import annotations

import functools

import numpy as np

from .logicle import LogicleParameters, logicle_forward, logicle_inverse
import matplotlib.ticker as mticker
from matplotlib import scale as mscale
from matplotlib.scale import ScaleBase
from matplotlib.ticker import FixedLocator, FuncFormatter
from matplotlib.transforms import Transform

_FLOW_TICKS = [
    -1_000_000,
    -100_000,
    -10_000,
    -1_000,
    -100,
    0,
    100,
    1_000,
    10_000,
    100_000,
    1_000_000,
]
_FLOW_LABELS = [
    "-10⁶",
    "-10⁵",
    "-10⁴",
    "-10³",
    "-10²",
    "0",
    "10²",
    "10³",
    "10⁴",
    "10⁵",
    "10⁶",
]
_TICK_MAP = dict(zip(_FLOW_TICKS, _FLOW_LABELS))


@functools.lru_cache(maxsize=128)
def _flow_fmt(x, pos):
    if x in _TICK_MAP:
        return _TICK_MAP[x]
    if x == 0:
        return "0"
    ax = abs(x)
    if ax >= 1e4:
        exp = int(round(np.log10(ax)))
        sup = str(exp).translate(str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻"))
        return f"-10{sup}" if x < 0 else f"10{sup}"
    return f"{int(x)}"


class _FlowScale(ScaleBase):
    def set_default_locators_and_formatters(self, axis):
        axis.set_major_locator(FixedLocator(_FLOW_TICKS))
        axis.set_major_formatter(FuncFormatter(_flow_fmt))
        axis.set_minor_locator(mticker.NullLocator())


class LegacyBiexpScale(_FlowScale):
    name = "legacy_biexp"

    def __init__(self, axis, **kw):
        super().__init__(axis)
        self.thresh = kw.pop("threshold", 1.0)

    def get_transform(self):
        return self._T(self.thresh)

    class _T(Transform):
        input_dims = output_dims = 1

        def __init__(self, t):
            Transform.__init__(self)
            self.t = t

        def transform_non_affine(self, a):
            return np.sign(a) * np.log1p(np.abs(a) / self.t) * self.t

        def inverted(self):
            return LegacyBiexpScale._Ti(self.t)

    class _Ti(Transform):
        input_dims = output_dims = 1

        def __init__(self, t):
            Transform.__init__(self)
            self.t = t

        def transform_non_affine(self, a):
            return np.sign(a) * (np.exp(np.abs(a) / self.t) - 1) * self.t

        def inverted(self):
            return LegacyBiexpScale._T(self.t)


class AsinhScale(_FlowScale):
    name = "asinh"

    def __init__(self, axis, **kw):
        super().__init__(axis)
        self.cofactor = kw.pop("cofactor", 150.0)

    def get_transform(self):
        return self._T(self.cofactor)

    class _T(Transform):
        input_dims = output_dims = 1

        def __init__(self, c):
            Transform.__init__(self)
            self.c = c

        def transform_non_affine(self, a):
            return np.arcsinh(a / self.c)

        def inverted(self):
            return AsinhScale._Ti(self.c)

    class _Ti(Transform):
        input_dims = output_dims = 1

        def __init__(self, c):
            Transform.__init__(self)
            self.c = c

        def transform_non_affine(self, a):
            return np.sinh(a) * self.c

        def inverted(self):
            return AsinhScale._T(self.c)


class LegacyLogicleScale(_FlowScale):
    name = "legacy_logicle"

    def __init__(self, axis, **kw):
        super().__init__(axis)
        self.cofactor = kw.pop("cofactor", 150.0)

    def get_transform(self):
        return self._T(self.cofactor)

    class _T(Transform):
        input_dims = output_dims = 1

        def __init__(self, c):
            Transform.__init__(self)
            self.c = c

        def transform_non_affine(self, a):
            return np.sign(a) * np.log10(1.0 + np.abs(a) / self.c)

        def inverted(self):
            return LegacyLogicleScale._Ti(self.c)

    class _Ti(Transform):
        input_dims = output_dims = 1

        def __init__(self, c):
            Transform.__init__(self)
            self.c = c

        def transform_non_affine(self, a):
            return np.sign(a) * (10 ** np.abs(a) - 1.0) * self.c

        def inverted(self):
            return LegacyLogicleScale._T(self.c)


class BiexpScale(LegacyBiexpScale):
    """Historical Matplotlib alias; preserves frozen vFlow behavior."""
    name = "biexp"


class LogicleScale(LegacyLogicleScale):
    """Historical Matplotlib alias; preserves frozen vFlow behavior."""
    name = "logicle"


class GatingMLLogicleScale(_FlowScale):
    """Equation-based Gating-ML 2.0 Logicle scale (T/W/M/A)."""
    name = "logicle_gml2"

    def __init__(self, axis, **kw):
        super().__init__(axis)
        self.params = LogicleParameters(
            T=kw.pop("T", 262144.0), W=kw.pop("W", 0.5),
            M=kw.pop("M", 4.5), A=kw.pop("A", 0.0))

    def get_transform(self):
        return self._T(self.params)

    class _T(Transform):
        input_dims = output_dims = 1

        def __init__(self, params):
            Transform.__init__(self)
            self.params = params

        def transform_non_affine(self, a):
            return logicle_forward(a, self.params)

        def inverted(self):
            return GatingMLLogicleScale._Ti(self.params)

    class _Ti(Transform):
        input_dims = output_dims = 1

        def __init__(self, params):
            Transform.__init__(self)
            self.params = params

        def transform_non_affine(self, a):
            return logicle_inverse(a, self.params)

        def inverted(self):
            return GatingMLLogicleScale._T(self.params)


def register_flow_scales():
    for cls in (LegacyBiexpScale, BiexpScale, AsinhScale, LegacyLogicleScale,
                LogicleScale, GatingMLLogicleScale):
        try:
            mscale.register_scale(cls)
        except Exception:
            pass

