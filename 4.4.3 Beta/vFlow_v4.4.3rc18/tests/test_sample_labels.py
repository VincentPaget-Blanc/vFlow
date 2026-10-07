from vflow.core.sample_labels import (
    make_sample_label,
    shorten_common_prefix_labels,
)


def test_make_sample_label_strips_path_extension_and_known_suffixes():
    assert (
        make_sample_label("/tmp/Mouse_A_TH-488_Pooled_CytoFile.csv")
        == "Mouse_A"
    )
    assert make_sample_label("Mouse_B___Results.csv") == "Mouse_B"
    assert make_sample_label("Mouse_C_CytoFile.csv") == "Mouse_C"


def test_make_sample_label_leaves_unknown_suffixes():
    assert make_sample_label("/tmp/Mouse_A_custom.csv") == "Mouse_A_custom"


def test_shorten_common_prefix_labels_strips_underscore_prefix():
    labels = ["experiment_day1_sampleA", "experiment_day1_sampleB"]

    assert shorten_common_prefix_labels(labels) == ["sampleA", "sampleB"]


def test_shorten_common_prefix_labels_keeps_short_or_single_labels():
    assert shorten_common_prefix_labels(["A_one", "A_two"]) == ["A_one", "A_two"]
    assert shorten_common_prefix_labels(["only_one"]) == ["only_one"]



def test_shorten_common_prefix_does_not_reduce_samples_to_bare_numbers():
    labels = ["plate_a_sample_1", "plate_a_sample_2"]
    assert shorten_common_prefix_labels(labels) == ["sample_1", "sample_2"]
