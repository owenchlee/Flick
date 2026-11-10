from gesture_control import smoother as sm


def _run(monkeypatch, size, pts):
    t = [0.0]
    monkeypatch.setattr(sm.time, "monotonic", lambda: t[0])
    f = sm.OneEuroSmoother(size=size)
    out = []
    for p in pts:
        t[0] += 1 / 30
        out.append(f.smooth(p))
    return f, out


def test_still_converges(monkeypatch):
    _, out = _run(monkeypatch, 7, [(100, 200)] * 30)
    assert out[-1] == (100, 200)


def test_fast_move_followed(monkeypatch):
    _, out = _run(monkeypatch, 7, [(0, 0)] * 10 + [(800, 400)] * 6)
    assert out[-1][0] > 600


def test_size_one_is_raw(monkeypatch):
    _, out = _run(monkeypatch, 1, [(0, 0), (50, 60)])
    assert out[-1] == (50, 60)


def test_reset_forgets_and_same_timestamp_ok(monkeypatch):
    f, _ = _run(monkeypatch, 7, [(0, 0)] * 5)
    f.reset()
    assert f.smooth((300, 300)) == (300, 300)
    assert f.smooth((310, 300))[0] >= 300  # same clock value, no crash
