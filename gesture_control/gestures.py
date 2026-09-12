"""Pure gesture-recognition logic.

Deliberately has zero dependency on MediaPipe, OpenCV, or any camera —
it operates on plain (x, y[, z]) normalized-coordinate tuples, one per hand
landmark, in MediaPipe Hands' standard 21-point order. That keeps this
module fast to unit test (see tests/test_gestures.py) and reusable if the
tracking backend ever changes.

Every threshold is expressed relative to the hand's own size (distance from
wrist to middle-finger knuckle), so detection quality doesn't drift as a
hand moves closer to or farther from the camera.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ─── MediaPipe Hands landmark indices ──────────────────────────────────────
WRIST = 0
THUMB_MCP, THUMB_TIP = 2, 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_MCP, RING_PIP, RING_TIP = 13, 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20

NUM_LANDMARKS = 21


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _finger_extended(landmarks, wrist, pip_idx: int, tip_idx: int, factor: float = 1.05) -> bool:
    """A finger reads as extended when its tip sits farther from the wrist
    than its own PIP joint does — robust to hand rotation/tilt, unlike a
    naive "tip.y < pip.y" check that only works on an upright hand."""
    return _dist(wrist, landmarks[tip_idx]) > _dist(wrist, landmarks[pip_idx]) * factor


@dataclass
class GestureState:
    cursor: tuple   # (x, y) normalized index-fingertip position
    active: dict    # gesture_id -> bool


def analyze(landmarks) -> GestureState:
    """landmarks: sequence of 21 (x, y[, z]) tuples, normalized 0..1."""
    if len(landmarks) < NUM_LANDMARKS:
        raise ValueError(f"expected {NUM_LANDMARKS} landmarks, got {len(landmarks)}")

    wrist = landmarks[WRIST]
    palm_size = max(_dist(wrist, landmarks[MIDDLE_MCP]), 1e-6)

    index_ext = _finger_extended(landmarks, wrist, INDEX_PIP, INDEX_TIP)
    middle_ext = _finger_extended(landmarks, wrist, MIDDLE_PIP, MIDDLE_TIP)
    ring_ext = _finger_extended(landmarks, wrist, RING_PIP, RING_TIP)
    pinky_ext = _finger_extended(landmarks, wrist, PINKY_PIP, PINKY_TIP)
    four_curled = not any((index_ext, middle_ext, ring_ext, pinky_ext))

    thumb_tip = landmarks[THUMB_TIP]
    thumb_mcp = landmarks[THUMB_MCP]
    thumb_ext = _dist(wrist, thumb_tip) > _dist(wrist, thumb_mcp) * 1.05
    vertical_margin = palm_size * 0.15
    thumb_points_up = thumb_tip[1] < thumb_mcp[1] - vertical_margin
    thumb_near_palm = _dist(thumb_tip, landmarks[INDEX_MCP]) < palm_size * 0.55

    thumbs_up = four_curled and thumb_ext and thumb_points_up
    fist = four_curled and thumb_near_palm
    peace = index_ext and middle_ext and not ring_ext and not pinky_ext
    # "Rock on" sign — index + pinky extended, middle/ring curled. Reserved
    # as a pose distinct from "point" (which only extends the index finger)
    # so it can carry its own dedicated action without any risk of firing
    # together with the point-driven flick gesture.
    rock = index_ext and pinky_ext and not middle_ext and not ring_ext

    if fist:
        # A tucked thumb inside a fist can incidentally satisfy the
        # thumbs-up geometry (it often sits above its own MCP) — a fist
        # should never also fire a like.
        thumbs_up = False

    # The default/idle pose: hand tracked, none of the named poses above —
    # this is what drives the phone-style swipe-to-scroll.
    point = not (thumbs_up or peace or fist or rock)

    return GestureState(
        cursor=(landmarks[INDEX_TIP][0], landmarks[INDEX_TIP][1]),
        active={
            "thumbs_up": thumbs_up,
            "peace": peace,
            "fist": fist,
            "rock": rock,
            "point": point,
        },
    )
