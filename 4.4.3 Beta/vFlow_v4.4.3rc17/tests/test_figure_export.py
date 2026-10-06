from vflow.services.figure_export import is_vector_path, save_figure


class FakeCollection:
    def __init__(self, rasterized):
        self.rasterized = rasterized
        self.history = []

    def get_rasterized(self):
        return self.rasterized

    def set_rasterized(self, value):
        self.history.append(value)
        self.rasterized = value


class FakeAxis:
    def __init__(self, collections):
        self.collections = collections


class FakeFigure:
    def __init__(self, collections=None, fail=False):
        self.collections = collections or []
        self.fail = fail
        self.saved = None

    def get_axes(self):
        return [FakeAxis(self.collections)]

    def get_facecolor(self):
        return "face"

    def savefig(self, path, **kwargs):
        self.saved = (path, kwargs)
        if self.fail:
            raise RuntimeError("boom")


def test_is_vector_path():
    assert is_vector_path("plot.pdf")
    assert is_vector_path("plot.SVG")
    assert not is_vector_path("plot.png")


def test_save_figure_uses_legacy_options():
    fig = FakeFigure()

    save_figure(fig, "plot.png")

    assert fig.saved == (
        "plot.png",
        {"dpi": 300, "bbox_inches": "tight", "facecolor": "face"},
    )


def test_save_figure_unrasterizes_vector_and_restores_state():
    coll = FakeCollection(True)
    fig = FakeFigure([coll])

    save_figure(fig, "plot.pdf", vector_unrasterize=True)

    assert coll.history == [False, True]
    assert coll.rasterized is True


def test_save_figure_restores_state_on_failure():
    coll = FakeCollection(True)
    fig = FakeFigure([coll], fail=True)

    try:
        save_figure(fig, "plot.pdf", vector_unrasterize=True)
    except RuntimeError:
        pass

    assert coll.history == [False, True]
    assert coll.rasterized is True

