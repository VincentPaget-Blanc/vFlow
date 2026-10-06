from vflow.ui.folder_state import get_last_folder, set_last_folder


def test_last_folder_state_roundtrip():
    set_last_folder("")
    assert get_last_folder() == ""

    set_last_folder("/tmp/example")
    assert get_last_folder() == "/tmp/example"

    set_last_folder(None)
    assert get_last_folder() == ""

