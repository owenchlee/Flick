"""Persisted app configuration: which action each gesture triggers, and
tracking sensitivity. Loaded by the tracker app, edited by the configurator
GUI, both reading/writing the same JSON file so changes made in one place
are picked up by the other.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

GESTURE_IDS = (
    "thumbs_up",
    "peace",
    "fist",
    "rock",
    "point",
)

GESTURE_LABELS = {
    "thumbs_up": "Thumbs up",
    "peace": "Peace sign",
    "fist": "Fist (hold)",
    "rock": "Rock sign",
    "point": "Point (flick up = next)",
}

DEFAULT_BINDINGS = {
    "thumbs_up": "like",
    "peace": "open_comments",
    "fist": "speed_2x",
    "rock": "scroll_prev",
    "point": "scroll",
}

# (min, max, default) — the configurator builds its sliders straight from this.
SETTINGS_RANGES = {
    "smoothing": (1, 20, 7),
    "action_cooldown": (0.30, 3.00, 1.00),
    "cursor_margin": (0.05, 0.40, 0.20),
    "scroll_sensitivity": (500, 6000, 2500),
    "flick_velocity": (0.5, 5.0, 1.8),
}


@dataclass
class Settings:
    camera_index: int = 0
    mirror: bool = True
    show_landmarks: bool = True
    show_grid: bool = False
    smoothing: int = SETTINGS_RANGES["smoothing"][2]
    action_cooldown: float = SETTINGS_RANGES["action_cooldown"][2]
    cursor_margin: float = SETTINGS_RANGES["cursor_margin"][2]
    scroll_sensitivity: int = SETTINGS_RANGES["scroll_sensitivity"][2]
    flick_velocity: float = SETTINGS_RANGES["flick_velocity"][2]

    def clamp(self) -> None:
        for name, (lo, hi, default) in SETTINGS_RANGES.items():
            value = getattr(self, name)
            # Cast using the field's declared type (from its default), not
            # the incoming value's type — an out-of-range int for a float
            # field must not silently truncate (e.g. int(0.15) == 0).
            setattr(self, name, type(default)(min(max(value, lo), hi)))


@dataclass
class AppConfig:
    bindings: dict = field(default_factory=lambda: dict(DEFAULT_BINDINGS))
    custom_hotkeys: dict = field(default_factory=dict)
    settings: Settings = field(default_factory=Settings)

    @classmethod
    def default(cls) -> "AppConfig":
        return cls()

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        bindings = dict(DEFAULT_BINDINGS)
        bindings.update(data.get("bindings", {}))
        bindings = {g: bindings.get(g, DEFAULT_BINDINGS[g]) for g in GESTURE_IDS}

        settings_data = data.get("settings", {})
        settings_fields = {f for f in Settings.__dataclass_fields__}
        settings = Settings(**{k: v for k, v in settings_data.items() if k in settings_fields})
        settings.clamp()

        return cls(
            bindings=bindings,
            custom_hotkeys=dict(data.get("custom_hotkeys", {})),
            settings=settings,
        )

    def to_dict(self) -> dict:
        return {
            "bindings": self.bindings,
            "custom_hotkeys": self.custom_hotkeys,
            "settings": asdict(self.settings),
        }


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig.default()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return AppConfig.default()
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, path: Path = CONFIG_PATH) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(config.to_dict(), fh, indent=2)
        fh.write("\n")
