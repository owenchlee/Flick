"""Renders the on-screen HUD drawn over the live camera feed.

OpenCV has no layout engine and only Hershey vector fonts, so "modern UI"
here means: translucent rounded panels, a small consistent color system
(gesture_control.theme), tight alignment, and restraint — not literal
componentry borrowed from web/app design.
"""

from __future__ import annotations

import time

import cv2

from . import theme
from .actions import ACTIONS
from .config import GESTURE_IDS, GESTURE_LABELS

FLASH_DURATION = 1.1
GESTURE_ORDER = list(GESTURE_IDS)


def _rounded_rect(img, top_left, bottom_right, color, radius=10, alpha=1.0):
    x1, y1 = top_left
    x2, y2 = bottom_right
    radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    layer = img if alpha >= 1.0 else img.copy()

    cv2.rectangle(layer, (x1 + radius, y1), (x2 - radius, y2), color, -1)
    cv2.rectangle(layer, (x1, y1 + radius), (x2, y2 - radius), color, -1)
    for cx, cy, start_angle in (
        (x1 + radius, y1 + radius, 180),
        (x2 - radius, y1 + radius, 270),
        (x1 + radius, y2 - radius, 90),
        (x2 - radius, y2 - radius, 0),
    ):
        cv2.ellipse(layer, (cx, cy), (radius, radius), start_angle, 0, 90, color, -1)

    if alpha < 1.0:
        cv2.addWeighted(layer, alpha, img, 1 - alpha, 0, img)


def draw_grid(frame):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    for i in range(1, 10):
        y = h * i // 10
        x = w * i // 10
        cv2.line(overlay, (0, y), (w, y), theme.BGR["border"], 1)
        cv2.line(overlay, (x, 0), (x, h), theme.BGR["border"], 1)
    cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)
    cv2.putText(frame, "GRID", (10, h - 50), theme.CV_FONT, 0.4, theme.BGR["text_muted"], 1, cv2.LINE_AA)


def draw_cursor(frame, point, active: bool):
    color = theme.BGR["success"] if active else theme.BGR["info"]
    cv2.circle(frame, point, 9, color, -1, cv2.LINE_AA)
    cv2.circle(frame, point, 13, theme.BGR["text"], 2, cv2.LINE_AA)


def _draw_top_bar(frame, w, hand_present: bool, fps: float):
    _rounded_rect(frame, (10, 10), (w - 10, 54), theme.BGR["surface"], radius=12, alpha=0.72)

    cv2.putText(frame, "THUMB", (24, 38), theme.CV_FONT_BOLD, 0.62, theme.BGR["text"], 1, cv2.LINE_AA)
    (tw, _), _ = cv2.getTextSize("THUMB", theme.CV_FONT_BOLD, 0.62, 1)
    cv2.putText(frame, "-DETECTOR", (24 + tw, 38), theme.CV_FONT_BOLD, 0.62, theme.BGR["brand_hover"], 1, cv2.LINE_AA)

    status_color = theme.BGR["success"] if hand_present else theme.BGR["disabled"]
    status_text = "HAND TRACKED" if hand_present else "NO HAND"
    (sw, _), _ = cv2.getTextSize(status_text, theme.CV_FONT, 0.48, 1)
    dot_x = w - 30 - sw - 90
    cv2.circle(frame, (dot_x, 30), 5, status_color, -1, cv2.LINE_AA)
    cv2.putText(frame, status_text, (dot_x + 12, 35), theme.CV_FONT, 0.48, theme.BGR["text_muted"], 1, cv2.LINE_AA)

    fps_text = f"{fps:4.1f} FPS"
    cv2.putText(frame, fps_text, (w - 100, 35), theme.CV_FONT, 0.48, theme.BGR["text_muted"], 1, cv2.LINE_AA)


def _draw_legend(frame, h, active: dict, bindings: dict):
    row_h = 22
    panel_h = row_h * len(GESTURE_ORDER) + 16
    top = h - panel_h - 46
    _rounded_rect(frame, (10, top), (272, top + panel_h), theme.BGR["surface"], radius=12, alpha=0.72)

    y = top + 24
    for gesture_id in GESTURE_ORDER:
        is_active = bool(active.get(gesture_id))
        dot_color = theme.BGR["success"] if is_active else theme.BGR["disabled"]
        cv2.circle(frame, (26, y - 4), 4, dot_color, -1, cv2.LINE_AA)

        label = GESTURE_LABELS[gesture_id]
        text_color = theme.BGR["text"] if is_active else theme.BGR["text_muted"]
        cv2.putText(frame, label, (38, y), theme.CV_FONT, 0.42, text_color, 1, cv2.LINE_AA)

        action_id = bindings.get(gesture_id, "none")
        action_label = ACTIONS[action_id].label if action_id in ACTIONS else "—"
        (aw, _), _ = cv2.getTextSize(action_label, theme.CV_FONT, 0.4, 1)
        cv2.putText(
            frame, action_label, (262 - aw, y), theme.CV_FONT, 0.4,
            theme.BGR["brand_hover"] if is_active else theme.BGR["text_muted"], 1, cv2.LINE_AA,
        )
        y += row_h


def _draw_bottom_bar(frame, w, h):
    _rounded_rect(frame, (10, h - 36), (w - 10, h - 10), theme.BGR["surface"], radius=10, alpha=0.72)
    hint = "G Grid   L Landmarks   R Reset   C Reload Config   Q Quit"
    cv2.putText(frame, hint, (24, h - 17), theme.CV_FONT, 0.42, theme.BGR["text_muted"], 1, cv2.LINE_AA)


def _draw_flash(frame, w, h, flash_text: str, flash_started_at: float):
    if not flash_text:
        return
    age = time.time() - flash_started_at
    if age > FLASH_DURATION:
        return
    alpha = max(0.0, 1.0 - (age / FLASH_DURATION))
    (tw, th), _ = cv2.getTextSize(flash_text, theme.CV_FONT_BOLD, 1.1, 2)
    cx, cy = w // 2, h // 2
    pad = 18
    _rounded_rect(
        frame,
        (cx - tw // 2 - pad, cy - th - pad // 2),
        (cx + tw // 2 + pad, cy + pad // 2),
        theme.BGR["surface"],
        radius=14,
        alpha=0.55 * alpha + 0.15,
    )
    color = tuple(int(c * alpha + b * (1 - alpha)) for c, b in zip(theme.BGR["success"], theme.BGR["surface"]))
    cv2.putText(frame, flash_text, (cx - tw // 2, cy), theme.CV_FONT_BOLD, 1.1, color, 2, cv2.LINE_AA)


def draw_hud(frame, *, fps: float, hand_present: bool, active: dict, bindings: dict,
             flash_text: str = "", flash_started_at: float = 0.0):
    h, w = frame.shape[:2]
    _draw_top_bar(frame, w, hand_present, fps)
    _draw_legend(frame, h, active, bindings)
    _draw_bottom_bar(frame, w, h)
    _draw_flash(frame, w, h, flash_text, flash_started_at)
