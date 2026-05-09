import time
import unittest
from unittest.mock import MagicMock, patch

from pulse.config import ActionConfig, PulseConfig, SequenceConfig
from pulse.events import GestureEvent
from pulse.gestures import Gesture
from pulse.handlers.recipe_handler import RecipeHandler


def _event(gesture: Gesture) -> GestureEvent:
    return GestureEvent(gesture=gesture)


def _make_handler(profiles=None, sequences=None):
    config = PulseConfig(
        profiles=profiles or {},
        sequences=sequences or [],
    )
    voice_trigger = MagicMock()
    handler = RecipeHandler(config, voice_trigger)
    return handler, voice_trigger


class TestRecipeHandlerSingleGesture(unittest.TestCase):
    def test_dispatches_profile_action(self):
        action = ActionConfig(type="dictate")
        profiles = {"default": {"fist": action}}
        handler, vt = _make_handler(profiles=profiles)

        with patch("pulse.handlers.recipe_handler.get_frontmost_app", return_value="default"), \
             patch("pulse.handlers.recipe_handler._execute_action") as mock_exec:
            handler(_event(Gesture.FIST))
            time.sleep(0.05)
            mock_exec.assert_called_once_with(action, vt)

    def test_unknown_gesture_ignored(self):
        handler, _ = _make_handler()
        with patch("pulse.handlers.recipe_handler._execute_action") as mock_exec:
            handler(_event(Gesture.UNKNOWN))
            time.sleep(0.05)
            mock_exec.assert_not_called()

    def test_rest_gesture_ignored(self):
        handler, _ = _make_handler()
        with patch("pulse.handlers.recipe_handler._execute_action") as mock_exec:
            handler(_event(Gesture.REST))
            time.sleep(0.05)
            mock_exec.assert_not_called()

    def test_app_specific_profile_overrides_default(self):
        default_action = ActionConfig(type="dictate")
        app_action = ActionConfig(type="type", text="hi")
        profiles = {
            "default": {"fist": default_action},
            "Terminal": {"fist": app_action},
        }
        handler, vt = _make_handler(profiles=profiles)

        with patch("pulse.handlers.recipe_handler.get_frontmost_app", return_value="Terminal"), \
             patch("pulse.handlers.recipe_handler._execute_action") as mock_exec:
            handler(_event(Gesture.FIST))
            time.sleep(0.05)
            mock_exec.assert_called_once_with(app_action, vt)

    def test_falls_back_to_default_when_app_not_matched(self):
        default_action = ActionConfig(type="dictate")
        profiles = {"default": {"fist": default_action}}
        handler, vt = _make_handler(profiles=profiles)

        with patch("pulse.handlers.recipe_handler.get_frontmost_app", return_value="Xcode"), \
             patch("pulse.handlers.recipe_handler._execute_action") as mock_exec:
            handler(_event(Gesture.FIST))
            time.sleep(0.05)
            mock_exec.assert_called_once_with(default_action, vt)


class TestRecipeHandlerSequences(unittest.TestCase):
    def test_sequence_fires_on_match(self):
        seq_action = ActionConfig(type="dictate")
        seq = SequenceConfig(gestures=["fist", "wave_out"], action=seq_action)
        handler, vt = _make_handler(sequences=[seq])

        with patch("pulse.handlers.recipe_handler._execute_action") as mock_exec:
            handler(_event(Gesture.FIST))
            handler(_event(Gesture.WAVE_OUT))
            time.sleep(0.05)
            mock_exec.assert_called_once_with(seq_action, vt)

    def test_timeout_flushes_as_single_gestures(self):
        seq_action = ActionConfig(type="dictate")
        seq = SequenceConfig(gestures=["fist", "wave_out"], action=seq_action)
        single_action = ActionConfig(type="type", text="x")
        profiles = {"default": {"fist": single_action}}
        handler, vt = _make_handler(profiles=profiles, sequences=[seq])

        with patch("pulse.handlers.recipe_handler.get_frontmost_app", return_value="default"), \
             patch("pulse.handlers.recipe_handler.SEQUENCE_TIMEOUT", 0.1), \
             patch("pulse.handlers.recipe_handler._execute_action") as mock_exec:
            handler(_event(Gesture.FIST))
            time.sleep(0.3)
            mock_exec.assert_called_once_with(single_action, vt)


if __name__ == "__main__":
    unittest.main()
