import pytest

pd = pytest.importorskip("pandas")

from vflow.services.batch_plot_samples import (
    build_batch_plot_samples,
    common_numeric_columns,
    first_distance_column,
    first_intensity_column,
    has_source_file_samples,
    preferred_distribution_column,
)


def test_has_source_file_samples_checks_only_active_paths():
    loaded = {
        "active.csv": pd.DataFrame({"X": [1]}),
        "inactive.csv": pd.DataFrame({"Source_File": ["a.csv"]}),
    }

    assert not has_source_file_samples(loaded, ["active.csv"])
    assert has_source_file_samples(loaded, ["inactive.csv"])


def test_build_batch_plot_samples_file_mode_uses_file_colors_and_sorted_paths():
    loaded = {
        "b_sample.csv": pd.DataFrame({"X": [2]}),
        "a_sample.csv": pd.DataFrame({"X": [1]}),
    }

    samples = build_batch_plot_samples(
        loaded_files=loaded,
        active_paths=["b_sample.csv", "a_sample.csv"],
        file_colors={"a_sample.csv": "red"},
        sample_colors=["blue", "green"],
    )

    assert [sample[0] for sample in samples] == ["a_sample", "b_sample"]
    assert [sample[2] for sample in samples] == ["red", "green"]


def test_build_batch_plot_samples_concat_mode_groups_source_file():
    loaded = {
        "pooled.csv": pd.DataFrame(
            {
                "Source_File": ["plate_a_sample_1.csv", "plate_a_sample_2.csv"],
                "X": [1, 2],
            }
        )
    }

    samples = build_batch_plot_samples(
        loaded_files=loaded,
        active_paths=["pooled.csv"],
        file_colors={},
        sample_colors=["blue", "green"],
    )

    assert [sample[0] for sample in samples] == ["sample_1", "sample_2"]
    assert [sample[2] for sample in samples] == ["blue", "green"]
    assert [sample[1]["X"].tolist() for sample in samples] == [[1], [2]]


def test_common_numeric_columns_excludes_label_and_index():
    frames = [
        pd.DataFrame({"Intensity": [1.0], "label": [1], "Text": ["a"]}),
        pd.DataFrame({"Intensity": [2.0], "index": [0], "Other": [3.0]}),
    ]

    assert common_numeric_columns(frames) == ["Intensity"]


def test_preferred_distribution_column_order():
    assert preferred_distribution_column(["Intensity_A", "Distance_A"]) == "Distance_A"
    assert preferred_distribution_column(["Intensity_A", "Other"]) == "Intensity_A"
    assert preferred_distribution_column(["Other"]) == "Other"
    assert preferred_distribution_column([]) == ""


def test_auto_column_helpers():
    cols = ["Other", "MeanIntensity", "Spot_dist"]

    assert first_intensity_column(cols) == "MeanIntensity"
    assert first_distance_column(cols) == "Spot_dist"
    assert first_intensity_column(["Other"]) is None
    assert first_distance_column(["Other"]) is None


def test_build_batch_plot_samples_mixed_concat_and_plain_keeps_both():
    loaded = {
        "pooled.csv": pd.DataFrame({
            "Source_File": ["a.csv", "b.csv"],
            "X": [1, 2],
        }),
        "plain.csv": pd.DataFrame({"X": [3]}),
    }
    samples = build_batch_plot_samples(
        loaded_files=loaded,
        active_paths=["pooled.csv", "plain.csv"],
        file_colors={"plain.csv": "red"},
        sample_colors=["blue", "green", "orange"],
    )

    assert len(samples) == 3
    assert sorted(int(sample[1]["X"].iloc[0]) for sample in samples) == [1, 2, 3]
    assert any(sample[2] == "red" and sample[1]["X"].tolist() == [3] for sample in samples)


def test_build_batch_plot_samples_does_not_merge_same_source_name_across_containers():
    loaded = {
        "pool_a.csv": pd.DataFrame({"Source_File": ["sample.csv"], "X": [1]}),
        "pool_b.csv": pd.DataFrame({"Source_File": ["sample.csv"], "X": [2]}),
    }
    samples = build_batch_plot_samples(
        loaded_files=loaded,
        active_paths=["pool_a.csv", "pool_b.csv"],
        file_colors={},
        sample_colors=["blue", "green"],
    )

    assert len(samples) == 2
    assert [sample[1]["X"].tolist() for sample in samples] == [[1], [2]]
    assert len({sample[0] for sample in samples}) == 2


def test_build_batch_plot_samples_uses_source_path_identity():
    loaded = {
        "pooled.csv": pd.DataFrame({
            "Source_File": ["sample.csv", "sample.csv"],
            "Source_Path": ["/a/sample.csv", "/b/sample.csv"],
            "X": [1, 2],
        })
    }
    samples = build_batch_plot_samples(
        loaded_files=loaded,
        active_paths=["pooled.csv"],
        file_colors={},
        sample_colors=["blue", "green"],
    )

    assert len(samples) == 2
    assert [sample[1]["X"].tolist() for sample in samples] == [[1], [2]]
    assert len({sample[0] for sample in samples}) == 2
