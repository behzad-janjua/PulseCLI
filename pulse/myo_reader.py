import logging
import sys
import time

from pyomyo import Myo, Pose, emg_mode

from pulse.dispatcher import Dispatcher
from pulse.events import GestureEvent
from pulse.gestures import Gesture

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 0.5

# Maps pyomyo's Pose enum to our Gesture enum.
# If gestures always log as UNKNOWN, run `python main.py --discover`
# to print the raw pose values and update this map.
POSE_MAP: dict[Pose, Gesture] = {
    Pose.REST: Gesture.REST,
    Pose.FIST: Gesture.FIST,
    Pose.WAVE_IN: Gesture.WAVE_IN,
    Pose.WAVE_OUT: Gesture.WAVE_OUT,
    Pose.FINGERS_SPREAD: Gesture.FINGERS_SPREAD,
    Pose.THUMB_TO_PINKY: Gesture.THUMB_TO_PINKY,
    Pose.UNKNOWN: Gesture.UNKNOWN,
}


class MyoReader:
    def __init__(self, dispatcher: Dispatcher, discover: bool = False) -> None:
        self._dispatcher = dispatcher
        self._discover = discover
        self._last_gesture: Gesture | None = None
        self._last_time: float = 0.0
        self._myo = Myo(mode=emg_mode.FILTERED)

    def _on_pose(self, pose: Pose) -> None:
        print(f"[RAW] pose callback fired: {pose!r}")  # temp debug
        if self._discover:
            # Print raw pyomyo values so you can verify POSE_MAP is correct.
            print(f"[DISCOVER] {pose!r}  type={type(pose).__name__}")
            return

        gesture = POSE_MAP.get(pose, Gesture.UNKNOWN)
        now = time.time()

        # Debounce: hardware fires the same pose repeatedly while held.
        # Drop the event if it's the same gesture within the cooldown window.
        if gesture == self._last_gesture and (now - self._last_time) < DEBOUNCE_SECONDS:
            return

        self._last_gesture = gesture
        self._last_time = now
        self._dispatcher.dispatch(GestureEvent(gesture=gesture))

    def start(self) -> None:
        try:
            self._myo.connect()
        except Exception as e:
            logger.error("MYO connection failed: %s\nIs the USB dongle plugged in?", e)
            sys.exit(1)

        self._myo.add_pose_handler(self._on_pose)
        logger.info("MYO connected. Listening for gestures... (Ctrl+C to stop)")

        try:
            while True:
                self._myo.run()
        except KeyboardInterrupt:
            pass
        finally:
            self._myo.disconnect()
            logger.info("MYO disconnected.")
