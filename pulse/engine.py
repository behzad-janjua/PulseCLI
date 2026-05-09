from __future__ import annotations

import logging
import threading
from typing import Callable

from pulse.config import load_config
from pulse.dispatcher import Dispatcher
from pulse.handlers.logger import log_event
from pulse.handlers.voice_trigger import VoiceTrigger
from pulse.handlers.window_navigator import navigate
from pulse.myo_reader import MyoReader
from pulse.voice_recorder import VoiceRecorder

logger = logging.getLogger(__name__)


class PulseEngine:
    """Owns all hardware and audio components. The UI talks only to this."""

    def __init__(self, discover: bool = False, use_custom: bool = False) -> None:
        self._state_cb:  Callable[[str], None] = lambda _: None
        self._action_cb: Callable[[str], None] = lambda _: None

        self._recorder      = VoiceRecorder(model_size="base")
        self._voice_trigger = VoiceTrigger(
            self._recorder,
            on_state=self._on_state,
            on_action=self._on_action,
        )

        dispatcher = Dispatcher()
        dispatcher.register(log_event)

        config = load_config()
        if config is not None:
            from pulse.handlers.recipe_handler import RecipeHandler
            dispatcher.register(RecipeHandler(config, self._voice_trigger))
            print("[PULSE] recipe mode — pulse.yaml loaded", flush=True)
        else:
            dispatcher.register(self._voice_trigger)
            dispatcher.register(navigate)

        self._reader = MyoReader(
            dispatcher,
            discover=discover,
            use_custom=use_custom,
            on_myo_state=self._on_state,
        )

    def on_state_change(self, callback: Callable[[str], None]) -> None:
        """Register a callback that receives state strings: disconnected / connected / recording / transcribing."""
        self._state_cb = callback

    def on_action(self, callback: Callable[[str], None]) -> None:
        """Register a callback that receives the last transcribed text."""
        self._action_cb = callback

    def start(self) -> None:
        """Start the MYO loop on a background thread."""
        t = threading.Thread(target=self._reader.start, daemon=True, name="myo-reader")
        t.start()

    def run_blocking(self) -> None:
        """Start the MYO loop on the calling thread (used for discover/debug mode)."""
        self._reader.start()

    def stop(self) -> None:
        """Shut down the MYO loop and release audio resources."""
        self._reader.stop()
        self._voice_trigger.close()

    def _on_state(self, state: str) -> None:
        self._state_cb(state)

    def _on_action(self, text: str) -> None:
        self._action_cb(text)
