"""Cursor smoothing.

A moving-average filter over the last N points removes frame-to-frame
tracking jitter at the cost of a little lag. Window size is user-tunable
(the configurator's "Smoothing" slider) since the right trade-off depends
on camera quality and personal preference.
"""

from __future__ import annotations

import math
import time
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
class OneEuroSmoother:
    """Adaptive low-pass (One Euro filter): heavy smoothing at rest, little while moving fast.

    Same interface as Smoother; `size` (the 1..20 slider) sets the resting cutoff.
    """

    BETA = 0.02  # cutoff gain per px/s of hand speed
    D_CUTOFF = 2.0  # Hz, smoothing of the speed estimate
    GAMMA = 1e-5  # extra cutoff gain per (px/s)^2: opens up fast on big sweeps
    SPEED_FLOOR = 60.0  # px/s of estimated speed treated as tracking noise

    def __init__(self, size: int = 7):
        self.resize(size)
        self.reset()

    def resize(self, size: int) -> None:
        self.size = max(1, size)
        # size 1 is raw; higher means a lower resting cutoff (steadier, more lag)
        self.min_cutoff = None if self.size <= 1 else 0.7 / self.size ** 1.3

    def reset(self) -> None:
        self._prev = None  # (t, filtered xy, filtered speed xy)

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def smooth(self, point: tuple) -> tuple:
        now = time.monotonic()
        x = (float(point[0]), float(point[1]))
        if self._prev is None or self.min_cutoff is None:
            self._prev = (now, x, (0.0, 0.0), x)
            return (int(x[0]), int(x[1]))
        t0, fx, fd, rx = self._prev
        dt = now - t0
        if dt <= 1e-4:  # identical or backwards timestamps: assume 30 fps
            dt = 1 / 30
        ad = self._alpha(self.D_CUTOFF, dt)
        d = [(x[i] - rx[i]) / dt for i in range(2)]
        fd = tuple(fd[i] + ad * (d[i] - fd[i]) for i in range(2))
        sp = max(0.0, math.hypot(*fd) - self.SPEED_FLOOR)
        cutoff = self.min_cutoff + self.BETA * sp + self.GAMMA * sp ** 2
        a = self._alpha(cutoff, dt)
        fx = tuple(fx[i] + a * (x[i] - fx[i]) for i in range(2))
        self._prev = (now, fx, fd, x)
        return (round(fx[0]), round(fx[1]))
