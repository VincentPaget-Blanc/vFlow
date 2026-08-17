import sys


def test_concat_paths_do_not_import_pandas():
    had_pandas = "pandas" in sys.modules

    import vflow.services.concat_paths  # noqa: F401

    if not had_pandas:
        assert "pandas" not in sys.modules


def test_concat_output_filename_and_path():
    from vflow.services.concat_paths import concat_output_filename, concat_save_path

    assert concat_output_filename(" pooled ") == "pooled.csv"
    assert concat_output_filename("pooled.CSV") == "pooled.CSV"
    assert concat_save_path("/tmp/out", "pooled") == "/tmp/out/pooled.csv"
