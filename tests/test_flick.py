"""Flick-to-advance must not fire on a hand that sweeps up into view."""
from types import SimpleNamespace

from gesture_control import app as app_module
from tests.test_shared_bindings import make


def feed(app, monkeypatch, samples, t0=100.0, dt=1 / 30):
    for i, (y, wrist_y) in enumerate(samples):
        monkeypatch.setattr(app_module.time, "monotonic", lambda t=t0 + i * dt: t)
        app._dispatch(SimpleNamespace(active={"point": True}, cursor=(0.5, y), wrist=(0.5, wrist_y), palm_size=0.1))


def fast_up(start):
    return [(start - 0.04 * i, start + 0.2 - 0.04 * i) for i in range(8)]


def test_hand_rising_into_view_does_not_flick(monkeypatch):
    app = make({"point": "scroll"})
    feed(app, monkeypatch, fast_up(0.8))
    assert "scroll" not in app.executor.calls


def test_flick_after_holding_still_fires(monkeypatch):
    app = make({"point": "scroll"})
    feed(app, monkeypatch, [(0.8, 1.0)] * 10 + fast_up(0.8))
    assert app.executor.calls == ["scroll"]
