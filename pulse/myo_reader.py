import logging
import struct
import sys
import threading
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
CONFIDENCE_THRESHOLD = 0.60  # minimum winning-class probability to count a window
VOTE_WINDOW = 3              # consecutive confident windows that must agree before emitting
_RETRAIN_WINDOW = 15         # rolling window size for retrain detection
_RETRAIN_THRESHOLD = 0.62    # avg raw confidence below this → needs_retrain

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
LEARNING_BUFFER_SIZE = WINDOW_SIZE * 8


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
        on_myo_state=None,
        on_gesture=None,
    ) -> None:
        self._dispatcher    = dispatcher
        self._discover      = discover
        self._use_custom    = use_custom
        self._raw_emg_mode   = use_custom
        self._on_myo_state  = on_myo_state or (lambda s: None)
        self._on_gesture    = on_gesture or (lambda s, c: None)
        self._stop_event    = threading.Event()
        self._last_gesture: Gesture | None = None
        self._last_label: str | None = None
        self._last_time: float = 0.0
        self._lock = threading.Lock()

        # EMG rolling buffer — used in both custom and hardware modes
        self._emg_buffer: deque = deque(maxlen=WINDOW_SIZE)
        self._learning_buffer: deque = deque(maxlen=LEARNING_BUFFER_SIZE)
        self._emg_step_count: int = 0
        self._prediction_votes: deque = deque(maxlen=VOTE_WINDOW)
        self._last_confidence: float | None = None
        self._raw_confidence_window: deque = deque(maxlen=_RETRAIN_WINDOW)

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
        label = (metadata or {}).get("custom_label") or gesture.value
        if (
            gesture == self._last_gesture
            and label == self._last_label
            and (now - self._last_time) < DEBOUNCE_SECONDS
        ):
            return
        self._last_gesture = gesture
        self._last_label = label
        self._last_time = now
        event = GestureEvent(gesture=gesture, metadata=metadata or {})
        self._on_gesture(label)
        self._dispatcher.dispatch(event)

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

        with self._lock:
            self._emg_buffer.append(emg)
            self._learning_buffer.append(emg)
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

        with self._lock:
            window = np.array(self._emg_buffer, dtype=np.float32)
        features = extract_features(window).reshape(1, -1)

        proba = self._clf.predict_proba(features)[0]
        confidence = float(proba.max())

        if confidence < CONFIDENCE_THRESHOLD:
            return

        label = self._le.inverse_transform([int(proba.argmax())])[0]
        self._prediction_votes.append(label)

        if len(self._prediction_votes) < VOTE_WINDOW:
            return
        if len(set(self._prediction_votes)) != 1:
            return

        try:
            gesture = Gesture(label)
            metadata = {"confidence": confidence}
        except ValueError:
            gesture = Gesture.UNKNOWN
            metadata = {"custom_label": label, "confidence": confidence}

        self._emit(gesture, metadata)

    def get_last_gesture_label(self) -> str | None:
        return self._last_label

    def get_recent_emg_window(self) -> np.ndarray | None:
        with self._lock:
            if len(self._emg_buffer) < WINDOW_SIZE:
                return None
            return np.array(self._emg_buffer, dtype=np.float32)

    def get_recent_emg_samples(self) -> np.ndarray | None:
        with self._lock:
            if not self._learning_buffer:
                return None
            return np.array(self._learning_buffer, dtype=np.float32)

    def reload_classifier(self) -> bool:
        if not self._raw_emg_mode:
            return False
        clf, le = _load_custom_classifier()
        if clf is None:
            return False
        self._clf = clf
        self._le = le
        self._use_custom = True
        self._prediction_votes.clear()
        logger.info("Custom classifier reloaded from models/")
        return True

    def stop(self) -> None:
        self._stop_event.set()

    def start(self) -> None:
        self._on_myo_state("connecting")
        try:
            self._myo.connect()
        except Exception as e:
            logger.error("MYO connection failed: %s\nIs the USB dongle plugged in?", e)
            self._on_myo_state("disconnected")
            sys.exit(1)

        self._myo.add_pose_handler(self._on_pose)
        self._myo.add_emg_handler(self._on_emg)

        mode = "custom classifier" if self._use_custom else "hardware classifier"
        logger.info("MYO connected [%s]. Listening... (Ctrl+C to stop)", mode)
        self._on_myo_state("connected")

        try:
            while not self._stop_event.is_set():
                try:
                    self._myo.run()
                except struct.error:
                    pass  # malformed BLE packet — skip and keep listening
                except Exception as e:
                    logger.warning("MYO read error: %s", e)
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self._myo.disconnect()
            self._on_myo_state("disconnected")
            logger.info("MYO disconnected.")
