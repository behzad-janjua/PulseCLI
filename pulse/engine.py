from __future__ import annotations

import logging
import threading
from typing import Callable

from pulse.config import load_config
from pulse.dispatcher import Dispatcher
from pulse.handlers.logger import log_event
from pulse.handlers.voice_trigger import VoiceTrigger
from pulse.handlers.window_navigator import navigate
from pulse.learning import LearningService, sanitize_label
from pulse.myo_reader import MyoReader
from pulse.voice_recorder import VoiceRecorder

logger = logging.getLogger(__name__)


class PulseEngine:
    """Owns all hardware and audio components. The UI talks only to this."""

    def __init__(self, discover: bool = False, use_custom: bool = False) -> None:
        self._state_cb:   Callable[[str], None] = lambda _: None
        self._action_cb:  Callable[[str], None] = lambda _: None
        self._gesture_cb: Callable[[str, float | None], None] = lambda l, c: None
        self._last_gesture: str | None = None
        self._learning = LearningService()
        self._config = None

        self._recorder      = VoiceRecorder(model_size="base")
        self._voice_trigger = VoiceTrigger(
            self._recorder,
            on_state=self._on_state,
            on_action=self._on_action,
        )

        dispatcher = Dispatcher()
        dispatcher.register(log_event)

        config = load_config()
        self._config = config
        if config is not None:
            from pulse.handlers.recipe_handler import RecipeHandler
            from pulse.window_targets import configure_focus_sets
            configure_focus_sets(config.focus_sets)
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
            on_gesture=self._on_gesture,
        )
        self._myo_thread: threading.Thread | None = None

    def on_state_change(self, callback: Callable[[str], None]) -> None:
        """Register a callback that receives state strings: disconnected / connected / recording / transcribing."""
        self._state_cb = callback

    def on_action(self, callback: Callable[[str], None]) -> None:
        """Register a callback that receives the last transcribed text."""
        self._action_cb = callback

    def on_gesture(self, callback: Callable[[str, float | None], None]) -> None:
        """Register a callback that receives (gesture_label, confidence | None)."""
        self._gesture_cb = callback

    def start(self) -> None:
        """Start the MYO loop on a background thread."""
        self._myo_thread = threading.Thread(target=self._reader.start, daemon=False, name="myo-reader")
        self._myo_thread.start()

    def run_blocking(self) -> None:
        """Start the MYO loop on the calling thread (used for discover/debug mode)."""
        self._reader.start()

    def stop(self) -> None:
        """Shut down the MYO loop and release audio resources."""
        self._reader.stop()
        if self._myo_thread is not None:
            self._myo_thread.join(timeout=3.0)
        self._voice_trigger.close()

    @property
    def use_custom(self) -> bool:
        return self._reader.use_custom

    @property
    def needs_retrain(self) -> bool:
        return self._reader.needs_retrain

    def get_active_profile(self, app: str) -> str | None:
        if self._config is None:
            return None
        if app in self._config.profiles:
            return app
        if "default" in self._config.profiles:
            return "default"
        return None

    def get_last_gesture(self) -> str | None:
        return self._last_gesture or self._reader.get_last_gesture_label()

    def correct_last_gesture(self, label: str) -> str:
        samples = self._reader.get_recent_emg_window()
        if samples is None:
            raise ValueError("No recent EMG window available yet")
        path = self._learning.save_sample(label, samples)
        safe_label = sanitize_label(label)
        self._on_action(f"Saved correction: {safe_label}")
        return str(path)

    def teach_gesture(self, label: str, trials: int = 3) -> list[str]:
        samples = self._reader.get_recent_emg_samples()
        if samples is None:
            raise ValueError("No recent EMG samples available yet")
        paths = self._learning.save_trials(label, samples, trials=trials)
        safe_label = sanitize_label(label)
        self._on_action(f"Saved {len(paths)} sample(s): {safe_label}")
        return [str(path) for path in paths]

    def retrain_model(self):
        self._on_state("retraining")
        try:
            result = self._learning.retrain()
            reloaded = self._reader.reload_classifier()  # also calls reset_retrain_flag
            suffix = "" if reloaded else " (restart with make custom)"
            self._on_action(
                f"Model updated: {len(result.classes)} gestures, {result.samples} windows{suffix}"
            )
            return result
        finally:
            self._on_state("connected")

    def _on_state(self, state: str) -> None:
        self._state_cb(state)

    def _on_action(self, text: str) -> None:
        self._action_cb(text)

    def _on_gesture(self, label: str, confidence: float | None = None) -> None:
        self._last_gesture = label
        self._gesture_cb(label, confidence)
