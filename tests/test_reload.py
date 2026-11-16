import pytest

from gesture_control.config import AppConfig, load_config, load_config_strict


@pytest.mark.parametrize("text", ["", "{", "[]", "[1, 2]", "{}"])  # wrong-shaped sections are tolerated by from_dict (keeps the good parts)
def test_strict_rejects_bad_files(tmp_path, text):
    p = tmp_path / "config.json"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_config_strict(p)
    assert load_config(p) == AppConfig.default()


def test_strict_missing_file_uses_defaults(tmp_path):
    assert load_config_strict(tmp_path / "nope.json") == AppConfig.default()
