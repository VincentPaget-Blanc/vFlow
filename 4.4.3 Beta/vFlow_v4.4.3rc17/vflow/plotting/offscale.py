"""Vectorized, renderer-only off-scale representation. Never mutate scientific values."""
import numpy as np
from matplotlib.collections import PathCollection
from vflow.core.transforms import forward_transform, inverse_transform


def classify(x, y, valid, xlim, ylim):
    valid = np.asarray(valid, bool)
    return {'x_low': int(np.count_nonzero(valid & (x < min(xlim)))),
        'x_high': int(np.count_nonzero(valid & (x > max(xlim)))),
        'y_low': int(np.count_nonzero(valid & (y < min(ylim)))),
        'y_high': int(np.count_nonzero(valid & (y > max(ylim))))}


def clamp_scatter_offsets(ax, offsets, inset_pixels=0.75):
    data = np.array(offsets, dtype=float, copy=True)
    if not len(data): return data
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    low = np.array([min(xlim), min(ylim)]); high = np.array([max(xlim), max(ylim)])
    finite = np.isfinite(data).all(axis=1)
    outside = finite & np.any((data < low) | (data > high), axis=1)
    data[outside] = np.clip(data[outside], low, high)
    if inset_pixels and outside.any():
        # Only boundary coordinates are inset; in-range coordinates remain bit-identical.
        points = ax.transData.transform(data[outside])
        bbox = ax.bbox
        points = np.clip(points, [bbox.x0+inset_pixels, bbox.y0+inset_pixels], [bbox.x1-inset_pixels, bbox.y1-inset_pixels])
        data[outside] = ax.transData.inverted().transform(points)
    return data


def edge_histogram(raw, valid, limits, scale, cofactor, params, bins=120):
    lo, hi = forward_transform(np.array(sorted(limits)), scale, cofactor, transform_params=params)
    edges_t = np.linspace(lo, hi, bins+1)
    transformed = forward_transform(np.asarray(raw)[valid], scale, cofactor, transform_params=params)
    counts, _ = np.histogram(np.clip(transformed, lo, hi), edges_t)
    edges = inverse_transform(edges_t, scale, cofactor, transform_params=params)
    return counts, edges


def finish_offscale_render(host, display, plot_type):
    """Final limits/transform are known here. KDE is computed on true values.

    Dot/Density markers are clamped after scientific color/density computation.
    Contour surfaces stay unchanged; explicit full-population edge counts prevent
    omitted out-of-view mass from being confused with absent events. Marginals use
    edge bins over the full transform-valid population when the view truncates it.
    """
    ax = host.ax
    counts = {k: 0 for k in ('x_low','x_high','y_low','y_high')}
    frames = []
    for path, df in display.items():
        if host.x_channel not in df or host.y_channel not in df: continue
        x = df[host.x_channel].to_numpy(float, copy=False); y = df[host.y_channel].to_numpy(float, copy=False)
        _, _, valid = host._transform_xy_cached(path, x, y)
        c = classify(x,y,valid,ax.get_xlim(),ax.get_ylim())
        for key in counts: counts[key] += c[key]
        frames.append((path,x,y,valid))
    for collection in ax.collections:
        if isinstance(collection, PathCollection) and collection.get_offsets().size:
            collection.set_offsets(clamp_scatter_offsets(ax, collection.get_offsets()))
    if any(counts.values()):
        text = f"Off-scale: X low {counts['x_low']:,} · X high {counts['x_high']:,} · Y low {counts['y_low']:,} · Y high {counts['y_high']:,}"
        ax.text(.01,.99,text,transform=ax.transAxes,va='top',fontsize=8,color=host.T['fg'],
            bbox={'facecolor':host.T['ax_bg'],'alpha':.8,'edgecolor':'none'})
        if host.ax_top is not None and host.ax_right is not None:
            for a in (host.ax_top,host.ax_right):
                for patch in list(a.patches):
                    if type(patch).__name__ in ('Polygon', 'StepPatch'): patch.remove()
            for path,x,y,valid in frames:
                for axis,raw,limits,scale,params,a in [
                    ('x',x,ax.get_xlim(),host.x_scale,host.x_transform_params,host.ax_top),
                    ('y',y,ax.get_ylim(),host.y_scale,host.y_transform_params,host.ax_right)]:
                    values,edges=edge_histogram(raw,valid,limits,scale,host.cofactor,params)
                    a.stairs(values,edges,orientation='vertical' if axis=='x' else 'horizontal',fill=True,
                        alpha=.25,color=host.file_colors[path])
                host.ax_top.relim();host.ax_top.autoscale_view(scalex=False,scaley=True)
                host.ax_right.relim();host.ax_right.autoscale_view(scalex=True,scaley=False)
        host.status_var.set(host.status_var.get()+'  │  '+text)
    return counts
