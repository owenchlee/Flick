"""Camera capture and MediaPipe HandLandmarker (Tasks API) wrapper.

MediaPipe's model load takes noticeably longer than opening a webcam, so it
loads on a background thread started immediately at construction — by the
time the camera is warmed up and the caller reaches `wait_until_ready()`,
the model is usually already loaded.

Uses the Tasks API (`mediapipe.tasks.python.vision.HandLandmarker`) rather
than the legacy `mp.solutions.hands`, which mediapipe removed in 1.0.
"""

from __future__ import annotations

import platform
import threading
import time
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
MODEL_PATH = Path(__file__).parent / "_models" / "hand_landmarker.task"


class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 30):
        import cv2

        system = platform.system()
        if system == "Windows":
            self._cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        elif system == "Darwin":
            self._cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
        else:
            self._cap = cv2.VideoCapture(index)

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def warm_up(self, frames: int = 5) -> None:
        for _ in range(frames):
            self._cap.read()

    def is_opened(self) -> bool:
        return self._cap.isOpened()

    def read(self):
        return self._cap.read()

    def release(self) -> None:
        self._cap.release()


def _ensure_model() -> None:
    if MODEL_PATH.exists():
        return
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = MODEL_PATH.with_suffix(".tmp")
    urllib.request.urlretrieve(MODEL_URL, tmp_path)
    tmp_path.replace(MODEL_PATH)


class _HandLandmarks:
    """Stand-in for the legacy `NormalizedLandmarkList` protobuf — gives the
    new API's plain landmark list a stable `.landmark` attribute so the rest
    of the app doesn't need to know the API migrated."""

    __slots__ = ("landmark",)

    def __init__(self, landmarks) -> None:
        self.landmark = landmarks


class _Result:
    __slots__ = ("multi_hand_landmarks",)

    def __init__(self, hand_landmarks_list) -> None:
        self.multi_hand_landmarks = (
            [_HandLandmarks(lms) for lms in hand_landmarks_list] if hand_landmarks_list else None
        )


class HandTracker:
    def __init__(self, max_num_hands: int = 1, min_detection_confidence: float = 0.7,
                 min_tracking_confidence: float = 0.7):
        self._mp = None
        self._landmarker = None
        self._connections = []
        self._start_time = time.monotonic()
        self._thread = threading.Thread(
            target=self._init,
            args=(max_num_hands, min_detection_confidence, min_tracking_confidence),
            daemon=True,
        )
        self._thread.start()

    def _init(self, max_num_hands, min_detection_confidence, min_tracking_confidence) -> None:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        _ensure_model()

        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._mp = mp
        self._connections = [
            (c.start, c.end) for c in vision.HandLandmarksConnections.HAND_CONNECTIONS
        ]
        self._landmarker = vision.HandLandmarker.create_from_options(options)

    def wait_until_ready(self) -> None:
        self._thread.join()

    def process(self, rgb_frame):
        rgb_frame.flags.writeable = False
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb_frame)
        timestamp_ms = int((time.monotonic() - self._start_time) * 1000)
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        rgb_frame.flags.writeable = True
        return _Result(result.hand_landmarks)

    def draw(self, frame, hand_landmarks) -> None:
        import cv2

        h, w = frame.shape[:2]
        points = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]
        for start, end in self._connections:
            cv2.line(frame, points[start], points[end], (200, 200, 200), 2)
        for x, y in points:
            cv2.circle(frame, (x, y), 4, (0, 200, 0), -1)

    @staticmethod
    def to_points(hand_landmarks):
        return [(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark]
