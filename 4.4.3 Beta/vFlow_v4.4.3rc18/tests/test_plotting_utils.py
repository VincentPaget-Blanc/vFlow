import pytest

np = pytest.importorskip("numpy")

from vflow.plotting.utils import (
    apply_sample_indices,
    evict_oldest_cache_entries,
    get_rng,
    gmm_component_label,
    gmm_overlay_curves,
    gmm_overlay_legend_layout,
    hex_to_rgba,
    sampled_indices,
    set_spines_color,
    threshold_band_boundaries,
    threshold_band_labels,
    valid_values,
)


def test_hex_to_rgba_supports_short_and_long_hex_and_is_immutable():
    rgba = hex_to_rgba("#abc", 0.5)

    np.testing.assert_allclose(rgba, np.array([0xAA / 255, 0xBB / 255, 0xCC / 255, 0.5]))
    assert rgba.dtype == np.float32
    assert rgba.flags.writeable is False

    np.testing.assert_allclose(hex_to_rgba("#112233", 1.0), np.array([0x11 / 255, 0x22 / 255, 0x33 / 255, 1.0]))


def test_hex_to_rgba_is_cached_by_arguments():
    assert hex_to_rgba("#abc", 0.5) is hex_to_rgba("#abc", 0.5)


def test_get_rng_restarts_generator_for_reproducible_seed():
    a = get_rng(123).integers(0, 1_000_000, size=8)
    b = get_rng(123).integers(0, 1_000_000, size=8)
    np.testing.assert_array_equal(a, b)

def test_sampled_indices_repeat_exactly_for_same_seed():
    np.testing.assert_array_equal(
        sampled_indices(100, 20, seed=7),
        sampled_indices(100, 20, seed=7),
    )


class FakeSpine:
    def __init__(self):
        self.color = None

    def set_color(self, color):
        self.color = color


class FakeAxis:
    def __init__(self):
        self.spines = {"left": FakeSpine(), "right": FakeSpine()}


def test_set_spines_color():
    axis = FakeAxis()

    set_spines_color(axis, "red")

    assert [spine.color for spine in axis.spines.values()] == ["red", "red"]


def test_sampling_helpers():
    values = np.arange(10)

    assert sampled_indices(5, 10, seed=1) is None
    idx = sampled_indices(10, 5, seed=1)

    assert len(idx) == 5
    assert len(set(idx.tolist())) == 5
    assert min(idx) >= 0
    assert max(idx) < 10
    sampled, = apply_sample_indices(values, indices=idx)
    assert sampled.tolist() == values[idx].tolist()
    unchanged, = apply_sample_indices(values, indices=None)
    assert unchanged is values


def test_valid_values():
    values = np.array([1.0, 2.0, 3.0])
    valid = np.array([True, False, True])

    assert valid_values(values, valid).tolist() == [1.0, 3.0]


def test_evict_oldest_cache_entries():
    cache = {idx: idx for idx in range(5)}

    evict_oldest_cache_entries(cache, max_entries=6, evict_count=2)
    assert list(cache) == [0, 1, 2, 3, 4]

    evict_oldest_cache_entries(cache, max_entries=5, evict_count=2)
    assert list(cache) == [2, 3, 4]


def test_gmm_overlay_labels_and_layout():
    assert gmm_component_label(0, 1234.5, 0.25) == "C1  \u03bc=1,234  w=0.25"
    assert gmm_overlay_legend_layout("horizontal", 4) == ((0.0, 1.0), "upper left", 2)
    assert gmm_overlay_legend_layout("vertical", 3) == ((1.0, 0.0), "lower right", 1)


def test_gmm_overlay_curves():
    scipy = pytest.importorskip("scipy")
    assert scipy
    params = {
        "means_t": [0.0],
        "means_raw": [0.0],
        "weights": [1.0],
        "stds_t": [1.0],
        "scale": "linear",
        "data_range_t": (-1.0, 1.0),
    }

    curves = gmm_overlay_curves(
        params,
        inverse_transform=lambda values, _scale: values,
        n_total=120,
        n_points=5,
    )

    assert len(curves) == 1
    assert curves[0]["x_raw"].tolist() == pytest.approx([-1.0, -0.5, 0.0, 0.5, 1.0])
    assert curves[0]["pdf_count"][2] > curves[0]["pdf_count"][0]
    assert curves[0]["color"] == "#ff6b6b"
    assert curves[0]["label"] == "C1  \u03bc=0  w=1.00"


def test_threshold_band_helpers():
    assert threshold_band_labels("TH", 0) == []
    assert threshold_band_labels("TH", 2) == ["TH\u2212", "TH+"]
    assert threshold_band_labels("TH", 3) == ["TH\u2212", "TH(m)", "TH+"]
    assert threshold_band_labels("TH", 4) == ["TH\u2212", "TH(m1)", "TH(m2)", "TH+"]
    assert threshold_band_boundaries((0.0, 10.0), [7.0, 3.0]) == [
        0.0,
        3.0,
        7.0,
        10.0,
    ]
