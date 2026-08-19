from dataclasses import FrozenInstanceError
import inspect

import pytest

from vflow.legacy.vflow_app import FlowApp
from vflow.rendering.flow_renderer import FlowRenderer
from vflow.rendering.render_plan import RenderPlan


class _Var:
    def __init__(self, value, calls=None, name=None):
        self.value = value
        self.calls = calls
        self.name = name

    def get(self):
        if self.calls is not None:
            self.calls.append(self.name)
        return self.value


def test_flow_app_render_surface_is_composed_and_lazy():
    source = inspect.getsource(FlowApp.refresh_plot)
    assert source.strip().endswith("return self._flow_renderer().refresh()")

    app = FlowApp.__new__(FlowApp)
    first = app._flow_renderer()
    second = app._flow_renderer()
    assert isinstance(first, FlowRenderer)
    assert first is second
    assert first._host is app


def test_render_plan_is_frozen_and_snapshots_structural_values():
    plan = RenderPlan(
        theme={"fg": "x"}, active={"a": 1}, display={"a": 2},
        applied_gates=(), effective_gate=False, need_marginals=False,
        plot_type="Dot Plot", dot_size=2, alpha=0.5, probability=0.05,
        x_channel="X", y_channel="Y", x_scale="linear", y_scale="asinh",
    )
    assert plan.plot_type == "Dot Plot"
    assert plan.y_scale == "asinh"
    with pytest.raises(FrozenInstanceError):
        plan.plot_type = "Density"


def test_refresh_materializes_render_plan_before_drawing_without_snapshotting_repeated_toggles():
    calls = []

    class Host:
        x_channel = "X"
        y_channel = "Y"
        x_scale = "linear"
        y_scale = "asinh"
        T = {"fig_bg": "f", "ax_bg": "a", "spine": "s"}
        ax_top = object()  # mismatch with False forces the setup branch
        ax_right = None
        gates = []
        show_marginals_var = _Var(False, calls, "marginals")
        plot_type_var = _Var("Density", calls, "plot_type")
        dot_size_var = _Var(3, calls, "dot_size")
        alpha_var = _Var(0.7, calls, "alpha")
        prob_var = _Var("5%", calls, "prob")

        def _active(self):
            import pandas as pd
            calls.append("active")
            return {"a.fcs": pd.DataFrame({"X": [1.0], "Y": [2.0]})}

        def _setup_axes(self):
            calls.append("setup_axes")

        def _update_cycle_label(self, active):
            calls.append("cycle")
            assert list(active) == ["a.fcs"]

        def _display_files(self, active):
            calls.append("display")
            return active

    renderer = FlowRenderer(Host())
    captured = {}

    def capture(plan):
        captured["plan"] = plan
        calls.append("render")
        return "sentinel"

    renderer.render = capture
    assert renderer.refresh() == "sentinel"
    plan = captured["plan"]
    assert plan.plot_type == "Density"
    assert plan.dot_size == 3
    assert plan.alpha == 0.7
    assert plan.probability == 0.05
    assert plan.x_channel == "X"
    assert plan.y_scale == "asinh"
    assert calls == [
        "active", "marginals", "setup_axes", "cycle", "display",
        "plot_type", "dot_size", "alpha", "prob", "render",
    ]

    # These historically repeated/late reads deliberately stay out of the plan.
    fields = set(RenderPlan.__dataclass_fields__)
    assert not {"fit_axes", "lock_scale", "show_legend", "show_grid", "show_labels"} & fields


def test_renderer_preserves_final_transform_label_lock_preview_flush_order():
    source = inspect.getsource(FlowRenderer.render)
    assert "host.plot_type_var" not in source
    assert "host.x_channel" not in source
    assert "host.y_channel" not in source
    assert "plan.x_channel" in source
    assert "plan.y_channel" in source
    assert "plan.x_scale" in source
    assert "plan.y_scale" in source

    positions = [
        source.index("host._set_axis_scale()"),
        source.index("self.draw_region_labels(applied_gates)"),
        source.index("host._apply_locked_limits()"),
        source.index("host._apply_minor_ticks()"),
        source.index("host._preview_gate()"),
        source.index("host.canvas.draw_idle()"),
    ]
    assert positions == sorted(positions)


def test_refresh_clears_stale_plot_when_active_files_have_no_valid_axes():
    calls = []

    class Axis:
        transAxes = object()
        def set_facecolor(self, value): calls.append(("face", value))
        def text(self, *args, **kwargs): calls.append(("text", args[2]))
        def set_xticks(self, value): calls.append(("xticks", tuple(value)))
        def set_yticks(self, value): calls.append(("yticks", tuple(value)))

    class Canvas:
        def draw_idle(self): calls.append("draw")

    class Status:
        def set(self, value): calls.append(("status", value))

    class Host:
        x_channel = None
        y_channel = None
        T = {"ax_bg": "a", "fg_dim": "d"}
        canvas = Canvas()
        status_var = Status()
        def _active(self):
            return {"a.csv": object(), "b.csv": object()}
        def _setup_axes(self):
            calls.append("setup")
            self.ax = Axis()

    FlowRenderer(Host()).refresh()
    assert calls[0] == "setup"
    assert any(item[0] == "text" and "No safe shared" in item[1]
               for item in calls if isinstance(item, tuple))
    assert calls[-1] == "draw"


def test_refresh_clears_stale_plot_instead_of_rendering_partial_file_subset():
    calls = []

    class Axis:
        transAxes = object()
        def set_facecolor(self, value): pass
        def text(self, *args, **kwargs): calls.append(args[2])
        def set_xticks(self, value): pass
        def set_yticks(self, value): pass

    class Canvas:
        def draw_idle(self): calls.append("draw")

    class Status:
        def set(self, value): calls.append(value)

    class Host:
        x_channel = "X"
        y_channel = "Y"
        T = {"ax_bg": "a", "fg_dim": "d"}
        canvas = Canvas()
        status_var = Status()
        def _active(self):
            import pandas as pd
            return {
                "a.csv": pd.DataFrame({"X": [1], "Y": [2]}),
                "b.csv": pd.DataFrame({"X": [3]}),
            }
        def _setup_axes(self): self.ax = Axis()

    renderer = FlowRenderer(Host())
    renderer.render = lambda plan: (_ for _ in ()).throw(
        AssertionError("partial subset must not reach render"))
    renderer.refresh()
    assert any("partial-file results" in str(item) for item in calls)
    assert calls[-1] == "draw"
