"""Two gestures bound to one hold/scroll action must share its state."""
from collections import deque
from types import SimpleNamespace

from gesture_control import app as app_module
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
    app._hold = {}
    app._flick_hist = deque()
    app._flick_armed = True
    app._flick_since = app._flick_prev_wrist = None
    app._flick_calm, app._flick_moving = 0.0, False
    app._reset_instant_state()
    return app


def run(app, monkeypatch, frames, active, t0, dt=0.05):
    t = t0
    for _ in range(frames):
        monkeypatch.setattr(app_module.time, "monotonic", lambda t=t: t)
        app._dispatch(SimpleNamespace(active=active, cursor=(0, 0.5), wrist=(0, 0), palm_size=1.0))
        t += dt
    return t


def test_shared_hold_stays_down_on_handover(monkeypatch):
    app = make({"fist": "speed_2x", "peace": "speed_2x"})
    t = run(app, monkeypatch, 5, {"fist": True}, 100.0)
    assert app.executor.calls == ["begin"]
    t = run(app, monkeypatch, 10, {"peace": True}, t)
    assert "end" not in app.executor.calls
    run(app, monkeypatch, 10, {}, t)
    assert app.executor.calls[-1] == "end"


def test_shared_scroll_keeps_flick_state_while_other_gesture_idle(monkeypatch):
    app = make({"point": "scroll", "rock": "scroll"})
    monkeypatch.setattr(app_module.time, "monotonic", lambda: 100.0)
    app._dispatch(SimpleNamespace(active={"point": True}, cursor=(0, 0.5), wrist=(0, 0), palm_size=1.0))
    app._flick_armed = False  # mid-flick, already fired
    # "rock" is checked before "point" each frame; being idle it must not
    # reset (and re-arm) the flick that "point" is still driving.
    monkeypatch.setattr(app_module.time, "monotonic", lambda: 100.25)
    app._dispatch(SimpleNamespace(active={"point": True}, cursor=(0, 0.2), wrist=(0, 0), palm_size=1.0))
    assert not app._flick_armed
    assert "scroll" not in app.executor.calls
