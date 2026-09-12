"""Cursor smoothing.

A moving-average filter over the last N points removes frame-to-frame
tracking jitter at the cost of a little lag. Window size is user-tunable
(the configurator's "Smoothing" slider) since the right trade-off depends
on camera quality and personal preference.
"""

from __future__ import annotations

from collections import deque


class Smoother:
    def __init__(self, size: int = 7):
        self.size = max(1, size)
        self._pts = deque(maxlen=self.size)

    def resize(self, size: int) -> None:
        self.size = max(1, size)
        pts = list(self._pts)[-self.size :]
        self._pts = deque(pts, maxlen=self.size)

    def reset(self) -> None:
        self._pts.clear()

    def smooth(self, point: tuple) -> tuple:
        self._pts.append(point)
        n = len(self._pts)
        sx = sum(p[0] for p in self._pts)
        sy = sum(p[1] for p in self._pts)
        return (int(sx / n), int(sy / n))
