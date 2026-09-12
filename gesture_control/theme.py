"""Shared design tokens for Thumb-Detector's two surfaces: the OpenCV HUD
overlay (video window) and the CustomTkinter configurator (settings window).

Keeping one palette in one place means the live overlay and the settings
window always look like the same product instead of two unrelated scripts.
"""

from __future__ import annotations


def hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
    """Convert a '#RRGGBB' hex string to an OpenCV-style BGR tuple."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return (b, g, r)


# ─── Palette (hex, RGB order — the source of truth) ───────────────────────
BACKGROUND = "#0F172A"       # app / window background
SURFACE = "#1E293B"          # panels, cards, HUD bars
SURFACE_MUTED = "#172033"    # recessed panels, inputs
BORDER = "#334155"           # dividers, card borders
TEXT = "#F8FAFC"             # primary text
TEXT_MUTED = "#94A3B8"       # secondary / caption text
DISABLED = "#475569"         # inactive gestures, disabled controls

BRAND = "#6366F1"            # primary accent — headings, active nav, brand mark
BRAND_HOVER = "#818CF8"

SUCCESS = "#22C55E"          # click / copy / positive confirmation
WARNING = "#F59E0B"          # paste / hold / cooldown-in-progress
DANGER = "#EF4444"           # quit / disabled / destructive
INFO = "#38BDF8"             # cursor dot, neutral tracking highlight

# ─── BGR variants for OpenCV drawing (cv2 is BGR, not RGB) ────────────────
BGR = {
    "background": hex_to_bgr(BACKGROUND),
    "surface": hex_to_bgr(SURFACE),
    "surface_muted": hex_to_bgr(SURFACE_MUTED),
    "border": hex_to_bgr(BORDER),
    "text": hex_to_bgr(TEXT),
    "text_muted": hex_to_bgr(TEXT_MUTED),
    "disabled": hex_to_bgr(DISABLED),
    "brand": hex_to_bgr(BRAND),
    "brand_hover": hex_to_bgr(BRAND_HOVER),
    "success": hex_to_bgr(SUCCESS),
    "warning": hex_to_bgr(WARNING),
    "danger": hex_to_bgr(DANGER),
    "info": hex_to_bgr(INFO),
}

# ─── Typography ────────────────────────────────────────────────────────────
# CustomTkinter (Windows-safe system font that reads like Inter's geometry).
UI_FONT_FAMILY = "Segoe UI"
UI_FONT_FAMILY_MONO = "Consolas"

# OpenCV only ships Hershey vector fonts — no custom font files.
CV_FONT = 0            # cv2.FONT_HERSHEY_SIMPLEX
CV_FONT_BOLD = 3       # cv2.FONT_HERSHEY_DUPLEX
