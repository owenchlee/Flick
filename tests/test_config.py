from gesture_control.config import (
    DEFAULT_BINDINGS,
    GESTURE_IDS,
    AppConfig,
    load_config,
    save_config,
)


def test_default_config_has_a_binding_for_every_gesture():
    config = AppConfig.default()
    assert set(config.bindings.keys()) == set(GESTURE_IDS)
    assert config.bindings == DEFAULT_BINDINGS


def test_missing_file_returns_defaults(tmp_path):
    config = load_config(tmp_path / "does-not-exist.json")
    assert config.bindings == DEFAULT_BINDINGS


def test_round_trip_save_and_load(tmp_path):
    path = tmp_path / "config.json"
    config = AppConfig.default()
    config.bindings["fist"] = "custom_hotkey"
    config.custom_hotkeys["peace"] = "ctrl+shift+s"
    config.settings.smoothing = 12
    config.settings.mirror = False

    save_config(config, path)
    reloaded = load_config(path)

    assert reloaded.bindings["fist"] == "custom_hotkey"
    assert reloaded.custom_hotkeys["peace"] == "ctrl+shift+s"
    assert reloaded.settings.smoothing == 12
    assert reloaded.settings.mirror is False


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json", encoding="utf-8")
    config = load_config(path)
    assert config.bindings == DEFAULT_BINDINGS


def test_unknown_gesture_ids_are_dropped_on_load():
    config = AppConfig.from_dict({"bindings": {"made_up_gesture": "left_click"}})
    assert "made_up_gesture" not in config.bindings
    assert set(config.bindings.keys()) == set(GESTURE_IDS)


def test_settings_are_clamped_to_their_valid_range():
    config = AppConfig.from_dict({"settings": {"smoothing": 999, "action_cooldown": -5}})
    assert config.settings.smoothing == 20
    assert config.settings.action_cooldown == 0.30
