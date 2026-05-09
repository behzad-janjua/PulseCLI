import logging

from pynput.keyboard import Controller, Key

from pulse.events import GestureEvent
from pulse.gestures import Gesture

logger = logging.getLogger(__name__)

_keyboard = Controller()


def navigate(event: GestureEvent) -> None:
    if event.gesture == Gesture.WAVE_OUT:
        with _keyboard.pressed(Key.cmd):
            _keyboard.tap(Key.tab)

    elif event.gesture == Gesture.WAVE_IN:
        with _keyboard.pressed(Key.cmd):
            with _keyboard.pressed(Key.shift):
                _keyboard.tap(Key.tab)

    elif event.gesture == Gesture.FINGERS_SPREAD:
        with _keyboard.pressed(Key.ctrl):
            _keyboard.tap(Key.up)
