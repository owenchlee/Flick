"""Persisted app configuration: which action each gesture triggers, and
tracking sensitivity. Loaded by the tracker app, edited by the configurator
GUI, both reading/writing the same JSON file so changes made in one place
are picked up by the other.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from gesture_control.actions import ACTIONS

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
    move_cursor: bool = True
    show_landmarks: bool = True
    show_grid: bool = False
    smoothing: int = SETTINGS_RANGES["smoothing"][2]
    action_cooldown: float = SETTINGS_RANGES["action_cooldown"][2]
    cursor_margin: float = SETTINGS_RANGES["cursor_margin"][2]
    scroll_sensitivity: int = SETTINGS_RANGES["scroll_sensitivity"][2]
    flick_velocity: float = SETTINGS_RANGES["flick_velocity"][2]

    def clamp(self) -> None:
        for name in ("mirror", "move_cursor", "show_landmarks", "show_grid"):
            if not isinstance(getattr(self, name), bool):
                setattr(self, name, type(self).__dataclass_fields__[name].default)
        cam = self.camera_index
        if isinstance(cam, float) and math.isfinite(cam) and cam == int(cam):
            cam = int(cam)
        self.camera_index = cam if type(cam) is int and cam >= 0 else 0
        for name, (lo, hi, default) in SETTINGS_RANGES.items():
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value):
                value = default
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
        if not isinstance(data, dict):
            data = {}
        raw = data.get("bindings")
        raw = raw if isinstance(raw, dict) else {}
        bindings = {
            g: raw[g] if isinstance(raw.get(g), str) and raw[g] in ACTIONS else DEFAULT_BINDINGS[g]
            for g in GESTURE_IDS
        }

        settings_data = data.get("settings")
        settings_data = settings_data if isinstance(settings_data, dict) else {}
        settings = Settings(**{k: v for k, v in settings_data.items() if k in Settings.__dataclass_fields__})
        settings.clamp()
        hotkeys = data.get("custom_hotkeys")
        hotkeys = hotkeys if isinstance(hotkeys, dict) else {}

        return cls(
            bindings=bindings,
            custom_hotkeys={k: v for k, v in hotkeys.items() if isinstance(k, str) and isinstance(v, str)},
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
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return AppConfig.default()
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, path: Path = CONFIG_PATH) -> None:
    # Write to a temp file in the same dir, then atomically replace the target.
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(config.to_dict(), fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
