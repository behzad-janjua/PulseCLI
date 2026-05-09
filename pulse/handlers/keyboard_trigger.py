import logging

from pynput.keyboard import Controller, Key

from pulse.events import GestureEvent
from pulse.gestures import Gesture

logger = logging.getLogger(__name__)

_keyboard = Controller()
_recording = False

# Gesture → action mapping:
#   FIST (1st)     = press Space  (start recording)
#   FIST (2nd)     = release Space (submit to Claude)
#   WAVE_OUT       = Escape (cancel / interrupt)
#   WAVE_IN        = Enter (confirm)
#   FINGERS_SPREAD = no action yet


def keyboard_trigger(event: GestureEvent) -> None:
    global _recording

    if event.gesture == Gesture.FIST:
        if not _recording:
            _keyboard.press(Key.space)
            _recording = True
            logger.info("[KEY] recording started")
        else:
            _keyboard.release(Key.space)
            _recording = False
            logger.info("[KEY] recording submitted")

    elif event.gesture == Gesture.WAVE_OUT:
        if _recording:
            _keyboard.release(Key.space)
            _recording = False
        logger.info("[KEY] Escape — interrupt")
        _keyboard.press(Key.esc)
        _keyboard.release(Key.esc)

    elif event.gesture == Gesture.WAVE_IN:
        logger.info("[KEY] Enter — confirm")
        _keyboard.press(Key.enter)
        _keyboard.release(Key.enter)
