import logging
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
from pyomyo import Myo, Pose, emg_mode

from pulse.dispatcher import Dispatcher
from pulse.events import GestureEvent
from pulse.gestures import Gesture

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 0.5

POSE_MAP: dict[Pose, Gesture] = {
    Pose.REST: Gesture.REST,
    Pose.FIST: Gesture.FIST,
    Pose.WAVE_IN: Gesture.WAVE_IN,
    Pose.WAVE_OUT: Gesture.WAVE_OUT,
    Pose.FINGERS_SPREAD: Gesture.FINGERS_SPREAD,
    Pose.THUMB_TO_PINKY: Gesture.THUMB_TO_PINKY,
    Pose.UNKNOWN: Gesture.UNKNOWN,
}

MODEL_DIR    = Path(__file__).parent.parent / "models"
WINDOW_SIZE  = 60   # samples (~300ms at 200Hz)
STEP_SIZE    = 30   # predict every ~150ms


def _load_custom_classifier():
    clf_path = MODEL_DIR / "gesture_classifier.pkl"
    le_path  = MODEL_DIR / "label_encoder.pkl"
    if not clf_path.exists():
        return None, None
    import joblib
    clf = joblib.load(clf_path)
    le  = joblib.load(le_path)
    logger.info("Custom classifier loaded from models/")
    return clf, le


class MyoReader:
    def __init__(
        self,
        dispatcher: Dispatcher,
        discover: bool = False,
        use_custom: bool = False,
    ) -> None:
        self._dispatcher  = dispatcher
        self._discover    = discover
        self._use_custom  = use_custom
        self._last_gesture: Gesture | None = None
        self._last_time: float = 0.0

        # EMG rolling buffer — used in both custom and hardware modes
        self._emg_buffer: deque = deque(maxlen=WINDOW_SIZE)
        self._emg_step_count: int = 0

        if use_custom:
            self._clf, self._le = _load_custom_classifier()
            if self._clf is None:
                logger.error("No trained model found. Run `make train` first.")
                sys.exit(1)
            self._myo = Myo(mode=emg_mode.RAW)
        else:
            self._clf, self._le = None, None
            self._myo = Myo(mode=emg_mode.FILTERED)

    def _emit(self, gesture: Gesture, metadata: dict | None = None) -> None:
        now = time.time()
        if gesture == self._last_gesture and (now - self._last_time) < DEBOUNCE_SECONDS:
            return
        self._last_gesture = gesture
        self._last_time = now
        self._dispatcher.dispatch(GestureEvent(gesture=gesture, metadata=metadata or {}))

    def _on_pose(self, pose: Pose) -> None:
        if self._use_custom:
            return  # hardware classifier disabled in custom mode

        if self._discover:
            print(f"[DISCOVER] {pose!r}  type={type(pose).__name__}")
            return

        self._emit(POSE_MAP.get(pose, Gesture.UNKNOWN))

    def _on_emg(self, emg: tuple, moving: int) -> None:
        if self._discover:
            return

        self._emg_buffer.append(emg)
        self._emg_step_count += 1

        if not self._use_custom:
            return

        if (
            len(self._emg_buffer) == WINDOW_SIZE
            and self._emg_step_count >= STEP_SIZE
        ):
            self._emg_step_count = 0
            self._predict_from_buffer()

    def _predict_from_buffer(self) -> None:
        from pulse.emg.features import extract_features

        window = np.array(self._emg_buffer, dtype=np.float32)
        features = extract_features(window).reshape(1, -1)
        label = self._le.inverse_transform(self._clf.predict(features))[0]

        try:
            gesture = Gesture(label)
            metadata = {}
        except ValueError:
            # Custom gesture not in the enum — carry the label in metadata
            gesture = Gesture.UNKNOWN
            metadata = {"custom_label": label}

        self._emit(gesture, metadata)

    def start(self) -> None:
        try:
            self._myo.connect()
        except Exception as e:
            logger.error("MYO connection failed: %s\nIs the USB dongle plugged in?", e)
            sys.exit(1)

        self._myo.add_pose_handler(self._on_pose)
        self._myo.add_emg_handler(self._on_emg)

        mode = "custom classifier" if self._use_custom else "hardware classifier"
        logger.info("MYO connected [%s]. Listening... (Ctrl+C to stop)", mode)

        try:
            while True:
                self._myo.run()
        except KeyboardInterrupt:
            pass
        finally:
            self._myo.disconnect()
            logger.info("MYO disconnected.")
