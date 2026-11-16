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
from .smoother import OneEuroSmoother

WINDOW_TITLE = "Thumb-Detector"
FRAME_W, FRAME_H = 640, 480
DEBOUNCE_S = 0.08  # pose must persist this long (and >= 2 frames) before acting
REARM_S = 0.1  # pose must be off this long before an instant action can re-fire
HOLD_GRACE_S = 0.18  # tolerate tracking dropouts/misreads while a hold is down


class GestureControlApp:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or load_config()

        self.executor = ActionExecutor()
        self.smoother = OneEuroSmoother(size=self.config.settings.smoothing)
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
        self._fps_started = time.monotonic()

        self._cooldowns = {gesture_id: 0.0 for gesture_id in GESTURE_IDS}
        self._edge: dict = {}
        self._hold: dict = {}
        # State for the point-driven "flick up to advance" scroll gesture —
        # see _dispatch's "scroll" branch.
        self._flick_hist = deque()
        self._flick_armed = True

    def _flash(self, text: str | None) -> None:
        if not text:
            return
        self.flash_text = text
        self.flash_started_at = time.monotonic()

    def run(self) -> None:
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0

        self.tracker = HandTracker()
        self.camera = Camera(index=self.config.settings.camera_index, width=FRAME_W, height=FRAME_H)
        self.camera.warm_up()
        self.tracker.wait_until_ready()

        if not self.camera.is_opened():
            index = self.config.settings.camera_index
            self.camera.release()
            raise RuntimeError(
                f"Could not open camera {index}. Close other apps using it, or pick another "
                "camera index in the configurator."
            )

        tracker_error_reported = False
        try:
            while self.camera.is_opened():
                ok, frame = self.camera.read()
                if not ok or frame is None:
                    # Keep keys responsive and avoid a 100% CPU spin on a dead read.
                    if not self._handle_keys():
                        break
                    time.sleep(0.02)
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
                try:
                    result = self.tracker.process(rgb)
                except RuntimeError as exc:
                    # One bad frame must not kill the app: treat it as "no hand".
                    result = None
                    if not tracker_error_reported:
                        print(f"Hand tracker failed on a frame ({exc}); continuing.")
                        tracker_error_reported = True

                state = None
                if result is not None and result.multi_hand_landmarks:
                    hand_landmarks = result.multi_hand_landmarks[0]
                    try:
                        state = analyze(HandTracker.to_points(hand_landmarks))
                    except ValueError as exc:
                        # Partial landmark list from the tracker: treat as "no hand".
                        if not tracker_error_reported:
                            print(f"Bad landmarks from tracker ({exc}); continuing.")
                            tracker_error_reported = True

                if state is not None:
                    hand_present = True
                    if self.show_landmarks:
                        self.tracker.draw(frame, hand_landmarks)
                    active = state.active

                    self._drive_cursor(frame, state)
                    self._dispatch(state)
                else:
                    self._tick_holds_no_hand()
                    self.smoother.reset()
                    self._cursor_history.clear()
                    self._flick_hist.clear()
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
                # The X button hides the window but imshow would re-create it: quit instead.
                if cv2.getWindowProperty(WINDOW_TITLE, cv2.WND_PROP_VISIBLE) < 1:
                    break
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
            self.executor.release_all_holds()
            self._hold.clear()
            self._edge.clear()
            self.smoother.resize(self.config.settings.smoothing)
            self._flash("CONFIG RELOADED")
        return True

    def _move_cursor(self, x, y) -> None:
        # UAC / secure desktop / locked screen make moveTo fail: skip, don't crash.
        try:
            pyautogui.moveTo(x, y)
        except (OSError, pyautogui.PyAutoGUIException) as exc:
            if not getattr(self, "_move_error_reported", False):
                print(f"Cannot move the cursor ({exc}); continuing.")
                self._move_error_reported = True

    def _drive_cursor(self, frame, state) -> None:
        # Only track/move while the index finger is actually extended
        # (point or peace) — thumbs_up/fist curl it toward the palm, and
        # updating the aim point then would drag the cursor off whatever
        # the user was pointing at right as the click fires.
        if state.active.get("point") or state.active.get("peace"):
            margin_x = FRAME_W * self.config.settings.cursor_margin
            margin_y = FRAME_H * self.config.settings.cursor_margin

            mapped_x = np.interp(state.cursor[0] * FRAME_W, [margin_x, FRAME_W - margin_x], [0, self.screen_w])
            # The wrist must stay in frame, so the fingertip can't get lower than
            # FRAME_H - (wrist-to-tip drop); pull the bottom bound up to that.
            bottom_y = max(margin_y + FRAME_H * 0.25, min(FRAME_H - margin_y, FRAME_H * (1 - state.reach)))  # floor keeps interp sane
            mapped_y = np.interp(state.cursor[1] * FRAME_H, [margin_y, bottom_y], [0, self.screen_h])
            mapped_x = np.clip(mapped_x, 0, self.screen_w)
            mapped_y = np.clip(mapped_y, 0, self.screen_h)

            sx, sy = self.smoother.smooth((mapped_x, mapped_y))
            self._move_cursor(sx, sy)
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
            self._move_cursor(*pre_curl_screen_xy)
            self._cursor_history.clear()

        if self._cursor_frame_px is not None:
            highlight = state.active.get("thumbs_up", False) or state.active.get("peace", False)
            draw_cursor(frame, self._cursor_frame_px, highlight)

    def _dispatch(self, state) -> None:
        now = time.monotonic()
        for gesture_id in GESTURE_IDS:
            action_id = self.config.bindings.get(gesture_id, "none")
            spec = ACTIONS.get(action_id)
            if spec is None or spec.id == "none":
                continue

            is_active = state.active.get(gesture_id, False)

            if spec.kind == "hold":
                self._step_hold(gesture_id, spec.id, is_active, now)
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
                    # tolerate a single dropped pose frame; reset after a real release
                    if not self._flick_hist or now - self._flick_hist[-1][0] > 0.2:
                        self._flick_hist.clear()
                        self._flick_armed = True
                    continue

                norm_y = self._normalized_y(state.cursor[1])
                # Velocity is the net displacement over a ~0.15 s window, not
                # one frame pair, so jitter and batched frames do not fire it.
                hist = self._flick_hist
                if hist and now - hist[-1][0] > 0.3:  # camera hiccup: start over
                    hist.clear()
                hist.append((now, norm_y))
                while len(hist) > 2 and now - hist[1][0] >= 0.15:
                    hist.popleft()
                span = now - hist[0][0]
                if span >= 0.05:
                    velocity = (norm_y - hist[0][1]) / span  # negative = moving up
                    fired_recently = (
                        now - self._cooldowns.get(gesture_id, 0.0) < self.config.settings.action_cooldown
                    )
                    big_enough = hist[0][1] - norm_y >= 0.05
                    if self._flick_armed and not fired_recently and big_enough and velocity < -self.config.settings.flick_velocity:
                        self.executor.scroll(spec.id, -self.config.settings.scroll_sensitivity)
                        self._flash("NEXT REEL")
                        self._cooldowns[gesture_id] = now
                        self._flick_armed = False
                    elif velocity > -self.config.settings.flick_velocity * 0.5:
                        self._flick_armed = True

                continue

            # Rising edge only: the pose must persist (debounce) and must have
            # been off for a while before it can fire again.
            st = self._edge.setdefault(gesture_id, {"on": None, "frames": 0, "off": None, "fired": False})
            if not is_active:
                if st["on"] is not None:
                    if st["off"] is None:
                        st["off"] = now
                    if not st["fired"] or now - st["off"] >= REARM_S:
                        st.update(on=None, frames=0, off=None, fired=False)
                continue
            st["off"] = None
            if st["on"] is None:
                st["on"] = now
            st["frames"] += 1
            if st["fired"] or st["frames"] < 2 or now - st["on"] < DEBOUNCE_S:
                continue
            st["fired"] = True

            if now - self._cooldowns.get(gesture_id, 0.0) < self.config.settings.action_cooldown:
                continue

            custom_hotkey = self.config.custom_hotkeys.get(gesture_id, "")
            scroll_amount = self.config.settings.scroll_sensitivity if spec.id == SCROLL_PREV else 0
            self._flash(self.executor.fire(spec.id, custom_hotkey=custom_hotkey, scroll_amount=scroll_amount))
            self._cooldowns[gesture_id] = now

    def _step_hold(self, gesture_id: str, spec_id: str, is_active: bool, now: float) -> None:
        h = self._hold.setdefault(gesture_id, {"on": None, "frames": 0, "off": None, "down": False})
        if is_active:
            h["off"] = None
            if h["down"]:
                return
            if h["on"] is None:
                h["on"] = now
            h["frames"] += 1
            if h["frames"] >= 2 and now - h["on"] >= DEBOUNCE_S:
                h["down"] = True
                self._flash(self.executor.begin_hold(spec_id))
            return
        if not h["down"]:
            h.update(on=None, frames=0)
            return
        if h["off"] is None:
            h["off"] = now
        if now - h["off"] >= HOLD_GRACE_S:
            self._flash(self.executor.end_hold(spec_id))
            h.update(on=None, frames=0, off=None, down=False)

    def _tick_holds_no_hand(self) -> None:
        now = time.time()
        for gesture_id in GESTURE_IDS:
            spec = ACTIONS.get(self.config.bindings.get(gesture_id, "none"))
            if spec is not None and spec.kind == "hold":
                self._step_hold(gesture_id, spec.id, False, now)

    def _normalized_y(self, raw_y: float) -> float:
        margin = self.config.settings.cursor_margin
        return float(np.clip((raw_y - margin) / (1 - 2 * margin), 0.0, 1.0))

    def _update_fps(self) -> None:
        self._fps_frames += 1
        elapsed = time.monotonic() - self._fps_started
        if elapsed >= 0.5:
            self.fps = self._fps_frames / elapsed
            self._fps_frames = 0
            self._fps_started = time.monotonic()
