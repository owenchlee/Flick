"""Two gestures bound to one hold/scroll action must share its state."""
from types import SimpleNamespace

from gesture_control.app import GestureControlApp


class Exec:
    def __init__(self):
        self.calls = []

    def begin_hold(self, a):
        self.calls.append("begin")
        return ""

    def end_hold(self, a):
        self.calls.append("end")
        return ""

    def scroll(self, a, amt):
        self.calls.append("scroll")


def make(bindings):
    app = GestureControlApp.__new__(GestureControlApp)
    app.config = SimpleNamespace(
        bindings=bindings,
        custom_hotkeys={},
        settings=SimpleNamespace(
            cursor_margin=0.0, action_cooldown=0.0, flick_velocity=1.0, scroll_sensitivity=1
        ),
    )
    app.executor = Exec()
    app._flash = lambda *_: None
    app._cooldowns = {}
    app._flick_prev_y = app._flick_prev_t = None
    app._flick_armed = True
    return app


def test_shared_hold_stays_down_on_handover():
    app = make({"fist": "speed_2x", "peace": "speed_2x"})
    app._dispatch(SimpleNamespace(active={"fist": True}, cursor=(0, 0)))
    app._dispatch(SimpleNamespace(active={"peace": True}, cursor=(0, 0)))
    assert "end" not in app.executor.calls
    app._dispatch(SimpleNamespace(active={}, cursor=(0, 0)))
    assert app.executor.calls[-1] == "end"


def test_shared_scroll_keeps_flick_state_while_other_gesture_idle():
    app = make({"point": "scroll", "rock": "scroll"})
    app._flick_prev_y, app._flick_prev_t = 0.5, 0.0
    app._dispatch(SimpleNamespace(active={"point": True}, cursor=(0, 0.5)))
    assert app._flick_prev_y is not None
