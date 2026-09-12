from gesture_control.smoother import Smoother


def test_averages_over_window():
    smoother = Smoother(size=3)
    smoother.smooth((0, 0))
    smoother.smooth((10, 0))
    result = smoother.smooth((20, 0))
    assert result == (10, 0)  # average of 0, 10, 20


def test_window_slides_once_full():
    smoother = Smoother(size=2)
    smoother.smooth((0, 0))
    smoother.smooth((10, 0))
    result = smoother.smooth((20, 0))
    assert result == (15, 0)  # oldest point (0) dropped -> avg(10, 20)


def test_reset_clears_history():
    smoother = Smoother(size=5)
    smoother.smooth((100, 100))
    smoother.reset()
    result = smoother.smooth((0, 0))
    assert result == (0, 0)


def test_resize_shrinks_window_without_crashing():
    smoother = Smoother(size=5)
    for i in range(5):
        smoother.smooth((i * 10, 0))  # history ends as [0, 10, 20, 30, 40]
    smoother.resize(2)  # keeps only the most recent 2: [30, 40]
    result = smoother.smooth((100, 0))  # appending evicts 30 -> [40, 100]
    assert result == (int((40 + 100) / 2), 0)
