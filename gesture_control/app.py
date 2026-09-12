"""Main application loop: ties the camera, hand tracker, gesture recognizer,
action executor, and HUD overlay together.

Gesture -> action dispatch is entirely config-driven (see config.py /
configurator): this loop never hardcodes "pinch means click" — it looks up
whatever ACTIONS the current bindings say, and dispatches generically based
on the action's `kind` (instant / hold / scroll). That's what lets the
configurator remap any gesture to any action without touching this file.
"""

from __future__ import annotations

import time
from collections import deque

import cv2
import numpy as np
import pyautogui

from .actions import ACTIONS, SCROLL_PREV, ActionExecutor
from .config import GESTURE_IDS, AppConfig, load_config
from .gestures import analyze
from .hand_tracker import Camera, HandTracker
from .overlay import draw_cursor, draw_grid, draw_hud
from .smoother import Smoother

WINDOW_TITLE = "Thumb-Detector"
FRAME_W, FRAME_H = 640, 480


class GestureControlApp:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or load_config()

        self.executor = ActionExecutor()
        self.smoother = Smoother(size=self.config.settings.smoothing)
        self.screen_w, self.screen_h = pyautogui.size()

        self.camera: Camera | None = None
        self.tracker: HandTracker | None = None

        # Last on-screen aim point, held from the most recent frame where the
        # index finger was actually extended (point/peace). Curling into
        # thumbs_up/fist moves the index-tip landmark toward the palm, so we
        # must stop updating this while curled or the click/crosshair would
        # jump off the target the user aimed at right as the action fires.
        self._cursor_frame_px: tuple[int, int] | None = None
        # Short history of (frame_px, screen_xy) samples recorded while
        # point/peace is active. When the hand curls into thumbs_up/fist,
        # the last handful of frames are contaminated by the curl motion
        # itself dragging the index tip toward the palm — the oldest
        # sample here (from just before the curl started) is used to
        # re-anchor the cursor instead of the drifted final frame.
        self._cursor_history: deque = deque(maxlen=6)

        self.show_landmarks = self.config.settings.show_landmarks
        self.show_grid = self.config.settings.show_grid

        self.flash_text = ""
        self.flash_started_at = 0.0

        self.fps = 0.0
        self._fps_frames = 0
        self._fps_started = time.time()

        self._cooldowns = {gesture_id: 0.0 for gesture_id in GESTURE_IDS}
        # State for the point-driven "flick up to advance" scroll gesture —
        # see _dispatch's "scroll" branch.
        self._flick_prev_y = None
        self._flick_prev_t = None
        self._flick_armed = True

    def _flash(self, text: str | None) -> None:
        if not text:
            return
        self.flash_text = text
        self.flash_started_at = time.time()

    def run(self) -> None:
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0

        self.tracker = HandTracker()
        self.camera = Camera(index=self.config.settings.camera_index, width=FRAME_W, height=FRAME_H)
        self.camera.warm_up()
        self.tracker.wait_until_ready()

        try:
            while self.camera.is_opened():
                ok, frame = self.camera.read()
                if not ok:
                    continue

                if self.config.settings.mirror:
                    frame = cv2.flip(frame, 1)

                if not self._handle_keys():
                    break

                if self.show_grid:
                    draw_grid(frame)

                active = {g: False for g in GESTURE_IDS}
                hand_present = False

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = self.tracker.process(rgb)

                if result.multi_hand_landmarks:
                    hand_present = True
                    hand_landmarks = result.multi_hand_landmarks[0]
                    if self.show_landmarks:
                        self.tracker.draw(frame, hand_landmarks)

                    points = HandTracker.to_points(hand_landmarks)
                    state = analyze(points)
                    active = state.active

                    self._drive_cursor(frame, state)
                    self._dispatch(state)
                else:
                    self.executor.release_all_holds()
                    self.smoother.reset()
                    self._cursor_history.clear()
                    self._flick_prev_y = None
                    self._flick_prev_t = None
                    self._flick_armed = True

                self._update_fps()
                draw_hud(
                    frame,
                    fps=self.fps,
                    hand_present=hand_present,
                    active=active,
                    bindings=self.config.bindings,
                    flash_text=self.flash_text,
                    flash_started_at=self.flash_started_at,
                )

                cv2.imshow(WINDOW_TITLE, frame)
                cv2.setWindowProperty(WINDOW_TITLE, cv2.WND_PROP_TOPMOST, 1)
        finally:
            self.executor.release_all_holds()
            if self.camera:
                self.camera.release()
            cv2.destroyAllWindows()

    # ─── Per-frame helpers ─────────────────────────────────────────────────
    def _handle_keys(self) -> bool:
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            return False
        if key == ord("g"):
            self.show_grid = not self.show_grid
        elif key == ord("l"):
            self.show_landmarks = not self.show_landmarks
        elif key == ord("r"):
            self.smoother.reset()
            self._flash("RESET")
        elif key == ord("c"):
            self.config = load_config()
            self.smoother.resize(self.config.settings.smoothing)
            self._flash("CONFIG RELOADED")
        return True

    def _drive_cursor(self, frame, state) -> None:
        # Only track/move while the index finger is actually extended
        # (point or peace) — thumbs_up/fist curl it toward the palm, and
        # updating the aim point then would drag the cursor off whatever
        # the user was pointing at right as the click fires.
        if state.active.get("point") or state.active.get("peace"):
            margin_x = FRAME_W * self.config.settings.cursor_margin
            margin_y = FRAME_H * self.config.settings.cursor_margin

            mapped_x = np.interp(state.cursor[0] * FRAME_W, [margin_x, FRAME_W - margin_x], [0, self.screen_w])
            mapped_y = np.interp(state.cursor[1] * FRAME_H, [margin_y, FRAME_H - margin_y], [0, self.screen_h])
            mapped_x = np.clip(mapped_x, 0, self.screen_w)
            mapped_y = np.clip(mapped_y, 0, self.screen_h)

            sx, sy = self.smoother.smooth((mapped_x, mapped_y))
            pyautogui.moveTo(sx, sy)
            frame_px = (int(state.cursor[0] * FRAME_W), int(state.cursor[1] * FRAME_H))
            self._cursor_frame_px = frame_px
            self._cursor_history.append((frame_px, (sx, sy)))
        elif self._cursor_history:
            # Just curled out of point/peace — re-anchor on the oldest
            # (pre-curl) sample and actually move the OS cursor there, so
            # the click that's about to fire lands where the user aimed,
            # not wherever the fingertip drifted to mid-curl.
            pre_curl_frame_px, pre_curl_screen_xy = self._cursor_history[0]
            self._cursor_frame_px = pre_curl_frame_px
            pyautogui.moveTo(*pre_curl_screen_xy)
            self._cursor_history.clear()

        if self._cursor_frame_px is not None:
            highlight = state.active.get("thumbs_up", False) or state.active.get("peace", False)
            draw_cursor(frame, self._cursor_frame_px, highlight)

    def _dispatch(self, state) -> None:
        now = time.time()
        for gesture_id in GESTURE_IDS:
            action_id = self.config.bindings.get(gesture_id, "none")
            spec = ACTIONS.get(action_id)
            if spec is None or spec.id == "none":
                continue

            is_active = state.active.get(gesture_id, False)

            if spec.kind == "hold":
                if is_active:
                    self._flash(self.executor.begin_hold(spec.id))
                else:
                    self._flash(self.executor.end_hold(spec.id))
                continue

            if spec.kind == "scroll":
                # "Point" advances to the next reel via a discrete upward
                # flick, not a continuous 1:1 drag — dragging required the
                # hand to stay lifted in frame the whole time, and lowering
                # a tired hand back down (even partially out of frame) read
                # as an accidental reverse-scroll. A flick fires one
                # fixed-size pulse and then disarms until the finger slows
                # back down, so calmly holding the same pointed-finger pose
                # (e.g. to aim before a thumbs-up) never triggers it.
                if not is_active:
                    self._flick_prev_y = None
                    self._flick_prev_t = None
                    self._flick_armed = True
                    continue

                norm_y = self._normalized_y(state.cursor[1])
                if self._flick_prev_y is not None:
                    dt = max(now - self._flick_prev_t, 1e-3)
                    velocity = (norm_y - self._flick_prev_y) / dt  # negative = moving up
                    fired_recently = (
                        now - self._cooldowns.get(gesture_id, 0.0) < self.config.settings.action_cooldown
                    )
                    if self._flick_armed and not fired_recently and velocity < -self.config.settings.flick_velocity:
                        self.executor.scroll(spec.id, -self.config.settings.scroll_sensitivity)
                        self._flash("NEXT REEL")
                        self._cooldowns[gesture_id] = now
                        self._flick_armed = False
                    elif velocity > -self.config.settings.flick_velocity * 0.5:
                        self._flick_armed = True

                self._flick_prev_y = norm_y
                self._flick_prev_t = now
                continue

            if not is_active:
                continue

            if now - self._cooldowns.get(gesture_id, 0.0) < self.config.settings.action_cooldown:
                continue

            custom_hotkey = self.config.custom_hotkeys.get(gesture_id, "")
            scroll_amount = self.config.settings.scroll_sensitivity if spec.id == SCROLL_PREV else 0
            self._flash(self.executor.fire(spec.id, custom_hotkey=custom_hotkey, scroll_amount=scroll_amount))
            self._cooldowns[gesture_id] = now

    def _normalized_y(self, raw_y: float) -> float:
        margin = self.config.settings.cursor_margin
        return float(np.clip((raw_y - margin) / (1 - 2 * margin), 0.0, 1.0))

    def _update_fps(self) -> None:
        self._fps_frames += 1
        elapsed = time.time() - self._fps_started
        if elapsed >= 0.5:
            self.fps = self._fps_frames / elapsed
            self._fps_frames = 0
            self._fps_started = time.time()
