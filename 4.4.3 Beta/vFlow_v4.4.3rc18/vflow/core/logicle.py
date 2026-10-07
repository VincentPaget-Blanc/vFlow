"""Standards-compatible Gating-ML 2.0 Logicle transform.

The transform is parameterized by ``T, W, M, A`` and uses the modified
biexponential equation described by the Gating-ML 2.0 specification and the
Logicle publications.  This module deliberately does not implement or claim
FlowJo's lookup-table Biex transform.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping

import numpy as np
from scipy.optimize import brentq


@dataclass(frozen=True)
class LogicleParameters:
    """Gating-ML Logicle parameters.

    Defaults are the conventional digital-flow values commonly used by Logicle
    implementations.  Values are always serialized explicitly by vFlow when
    the standards-compatible transform is selected.
    """

    T: float = 262144.0
    W: float = 0.5
    M: float = 4.5
    A: float = 0.0

    def __post_init__(self) -> None:
        T = float(self.T)
        W = float(self.W)
        M = float(self.M)
        A = float(self.A)
        if not all(np.isfinite(v) for v in (T, W, M, A)):
            raise ValueError("Logicle T/W/M/A must all be finite.")
        if T <= 0:
            raise ValueError("Logicle T must be > 0.")
        if M <= 0:
            raise ValueError("Logicle M must be > 0.")
        if W < 0 or W > M / 2.0:
            raise ValueError("Logicle W must satisfy 0 <= W <= M/2.")
        if A < -W or A > M - 2.0 * W:
            raise ValueError("Logicle A must satisfy -W <= A <= M-2W.")
        object.__setattr__(self, "T", T)
        object.__setattr__(self, "W", W)
        object.__setattr__(self, "M", M)
        object.__setattr__(self, "A", A)

    @classmethod
    def from_mapping(cls, value: Mapping | None) -> "LogicleParameters":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise ValueError("Logicle parameters must be an object containing T/W/M/A.")
        missing = [key for key in ("T", "W", "M", "A") if key not in value]
        if missing:
            raise ValueError(
                "Logicle parameters are missing: " + ", ".join(missing)
            )
        return cls(T=value["T"], W=value["W"], M=value["M"], A=value["A"])

    def as_dict(self) -> dict[str, float]:
        return {"T": self.T, "W": self.W, "M": self.M, "A": self.A}

    def cache_key(self) -> tuple[float, float, float, float]:
        return self.T, self.W, self.M, self.A


@dataclass(frozen=True)
class _LogicleCoefficients:
    params: LogicleParameters
    a: float
    b: float
    c: float
    d: float
    f: float
    x1: float
    x0: float

    def inverse(self, y) -> np.ndarray:
        y = np.asarray(y, dtype=float)
        # Evaluate around the exact zero location x1 using expm1.  The naive
        # form a*exp(by)-c*exp(-dy)-f loses precision because three large
        # terms cancel near zero for wide linear regions.
        u = y - self.x1
        p = self.a * np.exp(self.b * self.x1)
        q = self.c * np.exp(-self.d * self.x1)
        with np.errstate(over="ignore", invalid="ignore"):
            return p * np.expm1(self.b * u) - q * np.expm1(-self.d * u)

    def derivative(self, y) -> np.ndarray:
        y = np.asarray(y, dtype=float)
        u = y - self.x1
        p = self.a * np.exp(self.b * self.x1)
        q = self.c * np.exp(-self.d * self.x1)
        with np.errstate(over="ignore", invalid="ignore"):
            return (
                p * self.b * np.exp(self.b * u)
                + q * self.d * np.exp(-self.d * u)
            )


@lru_cache(maxsize=128)
def _coefficients(T: float, W: float, M: float, A: float) -> _LogicleCoefficients:
    p = LogicleParameters(T=T, W=W, M=M, A=A)
    denom = p.M + p.A
    # The parameter constraints imply denom > 0; keep an explicit guard for
    # malformed callers and future schema changes.
    if denom <= 0:
        raise ValueError("Logicle M+A must be > 0.")
    w = p.W / denom
    x2 = p.A / denom
    x1 = x2 + w
    x0 = x2 + 2.0 * w
    b = denom * np.log(10.0)

    if w == 0.0:
        d = b
    else:
        def root(d_value: float) -> float:
            return 2.0 * (np.log(d_value) - np.log(b)) + w * (d_value + b)

        # root(d) -> -inf as d -> 0+, and root(b) = 2*w*b > 0.
        d = brentq(root, np.finfo(float).tiny, b, xtol=1e-14, rtol=1e-14)

    ca = np.exp(x0 * (b + d))
    fa = np.exp(b * x1) - ca / np.exp(d * x1)
    a = p.T / (np.exp(b) - fa - ca / np.exp(d))
    c = ca * a
    f = fa * a
    return _LogicleCoefficients(p, float(a), float(b), float(c), float(d),
                                float(f), float(x1), float(x0))


def _coefs(params: LogicleParameters | Mapping | None) -> _LogicleCoefficients:
    p = params if isinstance(params, LogicleParameters) else LogicleParameters.from_mapping(params)
    return _coefficients(*p.cache_key())


def logicle_inverse(values, params: LogicleParameters | Mapping | None = None) -> np.ndarray:
    """Map Logicle display coordinates to raw measurement values exactly."""
    return _coefs(params).inverse(values)


def _scalar_bracketed_forward(x: float, coef: _LogicleCoefficients) -> float:
    """Robust scalar inverse of B(y)=x used only for Newton fallbacks."""
    if np.isnan(x):
        return np.nan
    if x == np.inf:
        return np.inf
    if x == -np.inf:
        return -np.inf

    def fn(y: float) -> float:
        return float(coef.inverse(np.array([y]))[0] - x)

    lo = coef.x1 - 1.0
    hi = coef.x1 + 1.0
    flo = fn(lo)
    fhi = fn(hi)
    # B is strictly increasing. Expand symmetrically until the target is
    # bracketed; even values beyond nominal [0,T] are therefore supported.
    step = 1.0
    for _ in range(64):
        if flo <= 0.0 <= fhi:
            return float(brentq(fn, lo, hi, xtol=1e-13, rtol=1e-13, maxiter=128))
        step *= 2.0
        if flo > 0.0:
            lo = coef.x1 - step
            flo = fn(lo)
        if fhi < 0.0:
            hi = coef.x1 + step
            fhi = fn(hi)
    raise RuntimeError("Could not bracket Logicle forward transform.")


def logicle_forward(values, params: LogicleParameters | Mapping | None = None) -> np.ndarray:
    """Map raw measurement values to Gating-ML Logicle coordinates.

    A vectorized Newton solve handles ordinary arrays efficiently. Any element
    that does not meet a strict residual criterion falls back to an independent
    monotonic bracketed solve, preventing a fast-iteration failure from silently
    returning the wrong coordinate.
    """
    coef = _coefs(params)
    x = np.asarray(values, dtype=float)
    out = np.empty_like(x, dtype=float)

    nan = np.isnan(x)
    posinf = np.isposinf(x)
    neginf = np.isneginf(x)
    finite = np.isfinite(x)
    out[nan] = np.nan
    out[posinf] = np.inf
    out[neginf] = -np.inf
    if not finite.any():
        return out

    xf = x[finite]
    # Stable piecewise seeds: linear around zero, asymptotic logarithmic seeds
    # outside the central region.
    deriv0 = float(coef.derivative(np.array([coef.x1]))[0])
    y = coef.x1 + xf / deriv0
    positive = xf > max(1.0, abs(coef.f))
    negative = xf < -max(1.0, abs(coef.f))
    if positive.any():
        with np.errstate(divide="ignore", invalid="ignore"):
            seed = np.log(np.maximum((xf[positive] + coef.f) / coef.a,
                                     np.finfo(float).tiny)) / coef.b
        y[positive] = seed
    if negative.any():
        with np.errstate(divide="ignore", invalid="ignore"):
            seed = -np.log(np.maximum((-xf[negative] - coef.f) / coef.c,
                                      np.finfo(float).tiny)) / coef.d
        y[negative] = seed

    # Newton on a strictly monotonic function. Clip individual steps to prevent
    # a poor asymptotic seed from crossing huge ranges in one iteration.
    for _ in range(10):
        value = coef.inverse(y)
        deriv = coef.derivative(y)
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            step = (value - xf) / deriv
        step = np.clip(step, -1.0, 1.0)
        good = np.isfinite(step)
        y[good] -= step[good]

    residual = np.abs(coef.inverse(y) - xf)
    tolerance = 2e-11 * np.maximum(1.0, np.abs(xf))
    converged = np.isfinite(y) & np.isfinite(residual) & (residual <= tolerance)
    if not np.all(converged):
        bad_indices = np.flatnonzero(~converged)
        for idx in bad_indices:
            y[idx] = _scalar_bracketed_forward(float(xf[idx]), coef)

    out[finite] = y
    return out


def validate_logicle_params(value: Mapping | LogicleParameters | None) -> dict[str, float]:
    """Validate and normalize a serialized parameter mapping."""
    return LogicleParameters.from_mapping(value).as_dict()
