from vflow.core.path_identity import file_identity_key, normalized_path


def test_symlink_and_target_share_file_identity(tmp_path):
    target = tmp_path / "target.csv"
    link = tmp_path / "link.csv"
    target.write_text("X\n1\n", encoding="utf-8")
    try:
        link.symlink_to(target)
    except OSError:
        return
    assert file_identity_key(target) == file_identity_key(link)
    assert normalized_path(link) == normalized_path(target)
