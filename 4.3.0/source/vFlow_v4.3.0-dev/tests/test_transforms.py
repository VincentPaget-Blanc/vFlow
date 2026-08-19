import pytest

np = pytest.importorskip("numpy")

from vflow.core.transforms import forward_transform, inverse_transform, transform_xy


@pytest.mark.parametrize("scale", ["linear", "asinh", "logicle", "biexp"])
def test_transform_roundtrip(scale):
    values = np.array([-1000.0, -10.0, 0.0, 10.0, 1000.0])

    transformed = forward_transform(values, scale, 150.0)
    restored = inverse_transform(transformed, scale, 150.0)

    np.testing.assert_allclose(restored, values, rtol=1e-10, atol=1e-10)


def test_log_transform_marks_non_positive_as_nan():
    transformed = forward_transform(np.array([-1.0, 0.0, 100.0]), "log", 150.0)

    assert np.isnan(transformed[0])
    assert np.isnan(transformed[1])
    assert transformed[2] == 2.0


def test_transform_xy_returns_finite_mask():
    xt, yt, finite = transform_xy([1.0, -1.0], [10.0, 100.0], "log", "linear")

    assert np.isfinite(xt[0])
    assert np.isnan(xt[1])
    assert list(yt) == [10.0, 100.0]
    assert list(finite) == [True, False]



def test_unknown_scale_is_rejected_instead_of_becoming_linear():
    with pytest.raises(ValueError):
        forward_transform(np.array([1.0]), "typo-scale", 150.0)

@pytest.mark.parametrize("scale", ["asinh", "logicle"])
@pytest.mark.parametrize("cofactor", [0.0, -1.0, float("nan")])
def test_invalid_cofactor_is_rejected(scale, cofactor):
    with pytest.raises(ValueError):
        forward_transform(np.array([1.0]), scale, cofactor)

def test_transform_xy_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        transform_xy([1.0, 2.0], [1.0], "linear", "linear")
