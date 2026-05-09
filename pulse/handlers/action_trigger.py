import logging
import subprocess

from pulse.events import GestureEvent
from pulse.gestures import Gesture

logger = logging.getLogger(__name__)

# Maps gestures to shell commands. Edit these to change what each gesture does.
# None means the gesture is intentionally ignored.
GESTURE_ACTIONS: dict[Gesture, str | None] = {
    Gesture.FIST:           "echo '[ACTION] activate'",
    Gesture.WAVE_OUT:       "echo '[ACTION] interrupt'",
    Gesture.WAVE_IN:        "echo '[ACTION] confirm'",
    Gesture.FINGERS_SPREAD: "echo '[ACTION] context'",
    Gesture.THUMB_TO_PINKY: "echo '[ACTION] mode_switch'",
    Gesture.REST:           None,
    Gesture.UNKNOWN:        None,
}


def trigger_action(event: GestureEvent) -> None:
    command = GESTURE_ACTIONS.get(event.gesture)
    if command is None:
        return

    logger.info("[TRIGGER] %s → %s", event.gesture.value, command)
    subprocess.Popen(command, shell=True)
