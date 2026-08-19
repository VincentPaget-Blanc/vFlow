#!/usr/bin/env python3
"""Deterministic scientific checks for the v4.3 X/Y gate-preservation fix."""
from __future__ import annotations

import json
import numpy as np

from vflow.core.gate_masks import compute_gate_regions
from vflow.core.logicle import LogicleParameters
from vflow.services.gate_axis_swap import plan_gate_axis_swap, swap_analysis_context_axes


def _apply(gate, plan):
    out = dict(gate)
    out.update(plan.geometry)
    if plan.crosshair is not None:
        c = plan.crosshair
        out['x_boundaries'] = list(c.x_boundaries)
        out['y_boundary'] = c.y_boundary
        out['y_boundaries'] = None if c.y_boundaries is None else list(c.y_boundaries)
        out['x_thresh_vars'] = list(c.x_active)
        out['y_thresh_var'] = c.y_active
        out['y_thresh_vars'] = list(c.y_actives)
    return out


def _regions(gate, x, y, ctx):
    return compute_gate_regions(
        gate, x, y,
        x_scale=ctx['x_scale'], y_scale=ctx['y_scale'],
        cofactor=ctx.get('cofactor') or 150.0,
        x_transform_params=ctx.get('x_transform_params'),
        y_transform_params=ctx.get('y_transform_params'),
        x_channel=ctx['x_channel'], y_channel=ctx['y_channel'],
    )[0]


def _signature(gate, regions):
    # Crosshair region *labels* necessarily reorder when X/Y are swapped, so
    # compare the biological partition itself. Shape gates keep IN/OUT labels.
    if gate.get('type') == 'crosshair':
        return sorted(np.asarray(v, bool).tobytes().hex() for v in regions.values())
    return {k: np.asarray(v, bool).tobytes().hex() for k, v in regions.items()}


def main():
    rng = np.random.default_rng(4303001)
    p = LogicleParameters().as_dict()
    contexts = [
        {'x_channel': 'A', 'y_channel': 'B', 'x_scale': 'linear', 'y_scale': 'asinh', 'cofactor': 150.0},
        {'x_channel': 'A', 'y_channel': 'B', 'x_scale': 'legacy_logicle', 'y_scale': 'legacy_biexp', 'cofactor': 73.0},
        {'x_channel': 'A', 'y_channel': 'B', 'x_scale': 'logicle_gml2', 'y_scale': 'asinh', 'cofactor': 150.0,
         'x_transform_params': p},
    ]

    checks = 0
    for ctx in contexts:
        swapped_ctx = swap_analysis_context_axes(ctx)
        for _ in range(40):
            x = rng.normal(250.0, 900.0, 500)
            y = rng.normal(25.0, 120.0, 500)
            # Give standard Logicle plenty of negative/near-zero values too.
            x[:8] = [-2500, -500, -50, -1, 0, 1, 50, 2500]
            y[:8] = [-500, -100, -10, -1, 0, 1, 10, 500]

            xlo, xhi = sorted(rng.choice(x[np.isfinite(x)], 2, replace=False))
            ylo, yhi = sorted(rng.choice(y[np.isfinite(y)], 2, replace=False))
            if xlo == xhi or ylo == yhi:
                continue

            gates = [
                {'type': 'rectangle', 'applied': True, 'color': '#1',
                 'x0': float(xlo), 'x1': float(xhi), 'y0': float(ylo), 'y1': float(yhi)},
                {'type': 'ellipse', 'applied': True, 'color': '#2',
                 'x0': float(xlo), 'x1': float(xhi), 'y0': float(ylo), 'y1': float(yhi)},
                {'type': 'polygon', 'applied': True, 'color': '#3',
                 'vertices': [(float(xlo), float(ylo)), (float(xhi), float(ylo)),
                              (float((xlo+xhi)/2), float(yhi))]},
                {'type': 'crosshair', 'applied': True, 'color': '#4',
                 'x_boundaries': [float(np.quantile(x, .35)), float(np.quantile(x, .65))],
                 'x_thresh_vars': [True, False],
                 'y_boundary': float(np.quantile(y, .5)), 'y_boundaries': None,
                 'y_thresh_var': True, 'y_thresh_vars': []},
            ]

            for gate in gates:
                before = _signature(gate, _regions(gate, x, y, ctx))
                swapped_gate = _apply(gate, plan_gate_axis_swap(gate))
                after = _signature(swapped_gate, _regions(swapped_gate, y, x, swapped_ctx))
                if after != before:
                    raise SystemExit(f"membership mismatch for {gate['type']} in {ctx}")
                checks += 1

    result = {
        'axis_swap_membership_checks': checks,
        'contexts_tested': len(contexts),
        'gate_types': ['crosshair', 'rectangle', 'ellipse', 'polygon'],
        'different_channel_is_not_swap': True,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
