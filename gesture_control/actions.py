"""Registry of actions a gesture can trigger, plus the executor that runs
them.

IO (mouse/keyboard) is injected via a `backend` dict rather than called
directly, so the registry and dispatch logic can be unit tested without
actually moving the system mouse or sending keystrokes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

ACTIONS: dict = {}


@dataclass(frozen=True)
class ActionSpec:
    id: str
    label: str
    category: str
    kind: str = "instant"  # "instant" | "hold" | "scroll"


def _register(action_id: str, label: str, category: str, kind: str = "instant") -> str:
    ACTIONS[action_id] = ActionSpec(action_id, label, category, kind)
    return action_id


NONE = _register("none", "Do nothing", "General")
LIKE = _register("like", "Like", "Reels")
OPEN_COMMENTS = _register("open_comments", "Open comments", "Reels")
SPEED_2X = _register("speed_2x", "2x speed", "Reels", "hold")
SCROLL = _register("scroll", "Next reel (flick up)", "Reels", "scroll")
SCROLL_PREV = _register("scroll_prev", "Previous reel", "Reels")
CUSTOM_HOTKEY = _register("custom_hotkey", "Custom hotkey…", "System")

# Status text flashed on the HUD when an instant action fires.
FLASH_LABELS = {
    LIKE: "LIKED",
    OPEN_COMMENTS: "COMMENTS",
    SCROLL_PREV: "PREV REEL",
}


def actions_by_category() -> dict:
    grouped: dict = {}
    for spec in ACTIONS.values():
        grouped.setdefault(spec.category, []).append(spec)
    return grouped


def default_backend() -> dict:
    import pyautogui
    import keyboard

    return {
        "click": pyautogui.click,
        "mouse_down": pyautogui.mouseDown,
        "mouse_up": pyautogui.mouseUp,
        "scroll": pyautogui.scroll,
        "hotkey": keyboard.send,
    }


class ActionExecutor:
    """Dispatches ActionSpecs to injected IO callables."""

    def __init__(self, backend: Optional[dict] = None):
        self.backend = backend if backend is not None else default_backend()
        self._held: set = set()

    def fire(self, action_id: str, custom_hotkey: str = "", scroll_amount: int = 0) -> Optional[str]:
        """Runs an instant action; returns a HUD status string, or None."""
        spec = ACTIONS.get(action_id)
        if spec is None or spec.id in (NONE, SPEED_2X, SCROLL):
            return None

        if spec.id == CUSTOM_HOTKEY:
            if not custom_hotkey:
                return None
            self.backend["hotkey"](custom_hotkey)
            return custom_hotkey.upper()

        if spec.id in (LIKE, OPEN_COMMENTS):
            self.backend["click"]()
        elif spec.id == SCROLL_PREV:
            if not scroll_amount:
                return None
            self.backend["scroll"](scroll_amount)
        else:
            return None

        return FLASH_LABELS.get(spec.id, spec.label.upper())

    def begin_hold(self, action_id: str) -> Optional[str]:
        if action_id == SPEED_2X and SPEED_2X not in self._held:
            self._held.add(SPEED_2X)
            self.backend["mouse_down"]()
            return "2X SPEED"
        return None

    def end_hold(self, action_id: str) -> Optional[str]:
        if action_id == SPEED_2X and SPEED_2X in self._held:
            self._held.discard(SPEED_2X)
            self.backend["mouse_up"]()
            return "NORMAL SPEED"
        return None

    def release_all_holds(self) -> None:
        for action_id in list(self._held):
            self.end_hold(action_id)

    def scroll(self, action_id: str, amount: int) -> None:
        if action_id == SCROLL and amount:
            self.backend["scroll"](amount)
