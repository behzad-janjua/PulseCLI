import logging
import subprocess
import threading

from pynput.keyboard import Controller

from pulse.events import GestureEvent
from pulse.gestures import Gesture
from pulse.voice_recorder import VoiceRecorder

logger = logging.getLogger(__name__)

_keyboard = Controller()

YELLOW = "\033[33m"
GREEN  = "\033[32m"
RED    = "\033[31m"
RESET  = "\033[0m"


class VoiceTrigger:
    def __init__(self, recorder: VoiceRecorder) -> None:
        self._recorder = recorder
        self._recording = False
        self._worker: threading.Thread | None = None
        self._claude_proc: subprocess.Popen | None = None

    def __call__(self, event: GestureEvent) -> None:
        if event.gesture == Gesture.FIST:
            if not self._recording:
                self._recording = True
                self._recorder.start()
                print(f"{YELLOW}[PULSE] recording...{RESET}", flush=True)
            else:
                self._recording = False
                print(f"{YELLOW}[PULSE] transcribing...{RESET}", flush=True)
                self._worker = threading.Thread(
                    target=self._transcribe_and_send, daemon=True
                )
                self._worker.start()

        elif event.gesture == Gesture.WAVE_OUT:
            self._handle_interrupt()

    def _transcribe_and_send(self) -> None:
        text = self._recorder.stop_and_transcribe()

        if not text:
            print(f"{RED}[PULSE] no speech detected{RESET}", flush=True)
            return

        print(f"{GREEN}[PULSE] → \"{text}\"{RESET}", flush=True)
        _keyboard.type(text)

    def _handle_interrupt(self) -> None:
        if self._recording:
            self._recording = False
            self._recorder.stop_and_transcribe()  # discard
            print(f"{RED}[PULSE] recording cancelled{RESET}", flush=True)
            return

        if self._claude_proc and self._claude_proc.poll() is None:
            self._claude_proc.terminate()
            print(f"{RED}[PULSE] claude interrupted{RESET}", flush=True)
