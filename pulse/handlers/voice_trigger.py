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
    def __init__(self, recorder: VoiceRecorder, on_state=None, on_action=None) -> None:
        self._recorder   = recorder
        self._on_state   = on_state  or (lambda s: None)
        self._on_action  = on_action or (lambda t: None)
        self._recording  = False
        self._worker: threading.Thread | None = None
        self._claude_proc: subprocess.Popen | None = None
        self._with_context: bool = False
        self._context_target: str | None = None

    def toggle_with_context(self, target: str | None = None) -> None:
        """Like toggle(), but appends a Context block to the transcribed text."""
        self._with_context = True
        self._context_target = target
        self.toggle()

    def toggle(self) -> None:
        """Start or stop recording. Called by RecipeHandler for 'dictate' actions."""
        if not self._recording:
            self._recording = True
            self._recorder.start()
            self._on_state("recording")
            print(f"{YELLOW}[PULSE] recording...{RESET}", flush=True)
        else:
            self._recording = False
            self._on_state("transcribing")
            print(f"{YELLOW}[PULSE] transcribing...{RESET}", flush=True)
            self._worker = threading.Thread(
                target=self._transcribe_and_send, daemon=True
            )
            self._worker.start()

    def cancel(self) -> None:
        """Cancel an in-progress recording."""
        if self._recording:
            self._recording = False
            self._recorder.stop_and_transcribe()  # discard
            self._on_state("connected")
            print(f"{RED}[PULSE] recording cancelled{RESET}", flush=True)

    def __call__(self, event: GestureEvent) -> None:
        if event.gesture == Gesture.FIST:
            self.toggle()

        elif event.gesture == Gesture.WAVE_OUT:
            self._handle_interrupt()

    def _transcribe_and_send(self) -> None:
        with_context = self._with_context
        context_target = self._context_target
        self._with_context = False
        self._context_target = None

        text = self._recorder.stop_and_transcribe()
        self._on_state("connected")

        if not text:
            print(f"{RED}[PULSE] no speech detected{RESET}", flush=True)
            return

        if with_context:
            from pulse.prompt_context import compose_prompt
            text = compose_prompt(text, context_target)

        print(f"{GREEN}[PULSE] → \"{text[:80]}{'...' if len(text) > 80 else ''}\"{RESET}", flush=True)
        self._on_action(text)
        _keyboard.type(text)

    def close(self) -> None:
        if self._recording:
            self._recording = False
            self._recorder.stop_and_transcribe()  # discard
        self._recorder.close()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2.0)

    def _handle_interrupt(self) -> None:
        if self._recording:
            self.cancel()
            return

        if self._claude_proc and self._claude_proc.poll() is None:
            self._claude_proc.terminate()
            print(f"{RED}[PULSE] claude interrupted{RESET}", flush=True)
