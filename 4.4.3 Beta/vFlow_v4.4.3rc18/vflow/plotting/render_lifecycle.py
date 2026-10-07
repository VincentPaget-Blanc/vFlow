"""Matplotlib refresh-lifecycle helpers for the main vFlow plot.

The legacy controller historically called ``Axes.clear()`` on every refresh.
That is semantically convenient, but it also discards the Axis/Tick artist
objects that Matplotlib can otherwise reuse.  AP04 keeps a deliberately narrow
"content reset" path for plot modes whose artists do not depend on the
pre-refresh transform during construction.

Contour Plot is intentionally excluded by the caller: ``Axes.clabel()`` chooses
label positions using the live transform while contour artists are created, so
preserving a nonlinear scale there would alter the historical image.  Plain
logarithmic axes are excluded as well because their live transform cannot accept
the historical temporary 0..1 fresh-axes limits used by this retained reset.
"""

from __future__ import annotations

from typing import Iterable


# Artist lists owned by Axes that represent refreshable plot content rather
# than the reusable Axis/Spine/Tick machinery.  Keep this explicit: removing
# every child would also delete axis labels, ticks, spines and the axes patch.
_REFRESH_ARTIST_LISTS = (
    "collections",
    "lines",
    "patches",
    "texts",
    "artists",
    "images",
    "tables",
)


def clear_data_artists_preserve_axis_state(ax) -> None:
    """Reset one Axes' plotted content while retaining Axis/Tick objects.

    The resulting data/autoscale state intentionally mirrors the parts of
    ``Axes.clear()`` that ``FlowApp.refresh_plot`` relies on:

    * all data/annotation artists and any legend are removed;
    * the default property cycle is restarted;
    * data limits are recomputed from an empty artist set;
    * view limits return to the historical fresh-axes unit box with autoscale
      enabled, allowing subsequently added scatter/patch artists to request the
      same autoscaling as after ``Axes.clear()``.

    Axis/Spine/Tick objects, scale machinery and formatter/locator allocations
    survive, which is the performance win this helper is designed to preserve.
    """
    for attr in _REFRESH_ARTIST_LISTS:
        try:
            artists = list(getattr(ax, attr))
        except Exception:
            continue
        for artist in artists:
            try:
                artist.remove()
            except Exception:
                # Match the refresh loop's historical fail-soft presentation
                # policy: one stale display artist must not abort a replot.
                pass

    legend = getattr(ax, "legend_", None)
    if legend is not None:
        try:
            legend.remove()
        except Exception:
            pass

    # Containers are bookkeeping wrappers (bar/errorbar/etc.) and are not
    # necessarily removed by deleting child artists.  vFlow's current main
    # plot does not create them, but clear the list to preserve clear()-like
    # semantics for future presentation-only artists.
    try:
        ax.containers.clear()
    except Exception:
        pass

    try:
        ax.set_prop_cycle(None)
    except Exception:
        pass

    # Public Matplotlib APIs only: relim() resets the empty dataLim; unit limits
    # reproduce a freshly-cleared Axes and auto=True restores autoscaling.  New
    # collections/patches then mark the shared view limits stale in the normal
    # Matplotlib way.
    try:
        ax.relim(visible_only=False)
    except Exception:
        pass
    try:
        ax.set_xlim(0.0, 1.0, auto=True)
    except Exception:
        pass
    try:
        ax.set_ylim(0.0, 1.0, auto=True)
    except Exception:
        pass




def can_preserve_axis_state(
    ax, *, plot_type: str, target_x_scale: str, target_y_scale: str
) -> bool:
    """Return whether the lightweight artist reset is safe for this frame.

    Reuse is intentionally forbidden across scale transitions: the retained
    Axis objects still carry the previous transform until the renderer applies
    the requested scale near the end of the pass.
    """
    if plot_type == "Contour Plot" or target_x_scale == "log" or target_y_scale == "log":
        return False
    try:
        return (
            ax.get_xscale() == target_x_scale
            and ax.get_yscale() == target_y_scale
        )
    except Exception:
        return False

def reset_refresh_axes(axes: Iterable, *, preserve_axis_state: bool) -> None:
    """Reset each non-None Axes using the requested refresh strategy."""
    for ax in axes:
        if ax is None:
            continue
        if preserve_axis_state:
            clear_data_artists_preserve_axis_state(ax)
        else:
            # ``Axes.clear()`` tries to restore fresh 0..1 limits before all
            # scale machinery is fully reset.  If the previous frame used a
            # logarithmic axis, Matplotlib rejects the zero limit and can
            # retain stale/reversed view limits into the next scale.  Explicit
            # temporary linearisation makes a full refresh truly fresh.  The
            # renderer reapplies the requested scale after plot construction.
            try:
                ax.set_xscale("linear")
            except Exception:
                pass
            try:
                ax.set_yscale("linear")
            except Exception:
                pass
            ax.clear()
