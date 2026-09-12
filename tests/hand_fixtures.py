"""Synthetic 21-point hand landmark builders for gesture-recognition tests.

Coordinates are plain (x, y, z) tuples in MediaPipe Hands' normalized,
image-coordinate convention (y grows downward, wrist near the bottom of
frame) — no MediaPipe/OpenCV import required to build or consume them.
"""

WRIST = (0.50, 0.90, 0.0)
THUMB_CMC = (0.42, 0.85, 0.0)
THUMB_MCP = (0.38, 0.78, 0.0)
THUMB_IP = (0.35, 0.72, 0.0)

INDEX_MCP = (0.45, 0.65, 0.0)
MIDDLE_MCP = (0.50, 0.64, 0.0)
RING_MCP = (0.55, 0.65, 0.0)
PINKY_MCP = (0.60, 0.67, 0.0)

INDEX_PIP = (0.45, 0.55, 0.0)
MIDDLE_PIP = (0.50, 0.54, 0.0)
RING_PIP = (0.55, 0.55, 0.0)
PINKY_PIP = (0.60, 0.59, 0.0)

INDEX_DIP = (0.45, 0.47, 0.0)
MIDDLE_DIP = (0.50, 0.46, 0.0)
RING_DIP = (0.55, 0.47, 0.0)
PINKY_DIP = (0.60, 0.53, 0.0)

# Distinct, unambiguous thumb-tip placements for each pose this file builds.
THUMB_UP = (0.30, 0.45, 0.0)
THUMB_NEAR_PALM = (0.44, 0.68, 0.0)
THUMB_NEUTRAL = (0.34, 0.80, 0.0)


def _tip(mcp, extended: bool):
    return (mcp[0], 0.30, 0.0) if extended else (mcp[0], mcp[1] + 0.02, 0.0)


def make_hand(
    index_ext: bool = False,
    middle_ext: bool = False,
    ring_ext: bool = False,
    pinky_ext: bool = False,
    thumb="neutral",
):
    """Builds a 21-landmark hand. `thumb` is one of "up", "near_palm", "neutral"."""
    index_tip = _tip(INDEX_MCP, index_ext)
    middle_tip = _tip(MIDDLE_MCP, middle_ext)
    ring_tip = _tip(RING_MCP, ring_ext)
    pinky_tip = _tip(PINKY_MCP, pinky_ext)

    thumb_positions = {
        "up": THUMB_UP,
        "near_palm": THUMB_NEAR_PALM,
        "neutral": THUMB_NEUTRAL,
    }
    thumb_tip = thumb_positions[thumb]

    return [
        WRIST,
        THUMB_CMC, THUMB_MCP, THUMB_IP, thumb_tip,
        INDEX_MCP, INDEX_PIP, INDEX_DIP, index_tip,
        MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, middle_tip,
        RING_MCP, RING_PIP, RING_DIP, ring_tip,
        PINKY_MCP, PINKY_PIP, PINKY_DIP, pinky_tip,
    ]
