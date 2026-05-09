import logging

from pynput.keyboard import Controller, Key

from pulse.events import GestureEvent
from pulse.gestures import Gesture

logger = logging.getLogger(__name__)

_keyboard = Controller()

# Gesture → keyboard action mapping:
#   FIST          = hold Space  (start Claude voice recording)
#   REST          = release Space (submit recording to Claude)
#   WAVE_OUT      = Escape (cancel / interrupt Claude)
#   WAVE_IN       = Enter (confirm)
#   FINGERS_SPREAD = no action yet


def keyboard_trigger(event: GestureEvent) -> None:
    if event.gesture == Gesture.FIST:
        logger.info("[KEY] Space held — recording")
        _keyboard.press(Key.space)

    elif event.gesture == Gesture.REST:
        _keyboard.release(Key.space)

    elif event.gesture == Gesture.WAVE_OUT:
        logger.info("[KEY] Escape — interrupt")
        _keyboard.press(Key.esc)
        _keyboard.release(Key.esc)

    elif event.gesture == Gesture.WAVE_IN:
        logger.info("[KEY] Enter — confirm")
        _keyboard.press(Key.enter)
        _keyboard.release(Key.enter)
