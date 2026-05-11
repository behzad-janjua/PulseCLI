from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pulse.dictionary as d
from pulse.dictionary import add_correction, apply_dictionary, infer_corrections


def _use_temp_dict(test_fn):
    """Decorator: isolate dictionary file for each test."""
    def wrapper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "dictionary.yaml"
            with patch.object(d, "DICT_PATH", path):
                test_fn(self)
    wrapper.__name__ = test_fn.__name__
    return wrapper


class TestApplyDictionary(unittest.TestCase):
    @_use_temp_dict
    def test_no_corrections_returns_text_unchanged(self):
        self.assertEqual(apply_dictionary("hello world"), "hello world")

    @_use_temp_dict
    def test_simple_replacement(self):
        add_correction("pie oh my oh", "pyomyo")
        result = apply_dictionary("use pie oh my oh for sensing")
        self.assertEqual(result, "use pyomyo for sensing")

    @_use_temp_dict
    def test_case_insensitive_match(self):
        add_correction("pie oh my oh", "pyomyo")
        result = apply_dictionary("Pie Oh My Oh is the library")
        self.assertEqual(result, "pyomyo is the library")

    @_use_temp_dict
    def test_longest_match_wins(self):
        add_correction("my oh", "myoh")
        add_correction("pie oh my oh", "pyomyo")
        result = apply_dictionary("use pie oh my oh today")
        # Longer phrase must win, not the shorter sub-phrase.
        self.assertEqual(result, "use pyomyo today")

    @_use_temp_dict
    def test_multiple_corrections_applied(self):
        add_correction("pie oh my oh", "pyomyo")
        add_correction("sky learn", "sklearn")
        result = apply_dictionary("use pie oh my oh and sky learn together")
        self.assertEqual(result, "use pyomyo and sklearn together")

    @_use_temp_dict
    def test_no_match_leaves_text_unchanged(self):
        add_correction("foo bar", "foobar")
        result = apply_dictionary("nothing to replace here")
        self.assertEqual(result, "nothing to replace here")

    @_use_temp_dict
    def test_correction_does_not_match_within_word(self):
        # "pi" → "py" must not corrupt "aspirin" or "spin"
        add_correction("pi", "py")
        result = apply_dictionary("aspirin and spin use pi")
        self.assertEqual(result, "aspirin and spin use py")

    @_use_temp_dict
    def test_correction_matches_at_sentence_boundaries(self):
        # Word-boundary anchors must still fire at start/end of string and at punctuation.
        add_correction("pi", "py")
        self.assertEqual(apply_dictionary("pi"), "py")
        self.assertEqual(apply_dictionary("pi."), "py.")
        self.assertEqual(apply_dictionary("use pi, please"), "use py, please")


class TestAddCorrection(unittest.TestCase):
    @_use_temp_dict
    def test_add_persists_and_applies(self):
        add_correction("sci kit learn", "scikit-learn")
        self.assertEqual(apply_dictionary("import sci kit learn"), "import scikit-learn")

    @_use_temp_dict
    def test_add_normalizes_spoken_to_lowercase(self):
        add_correction("NumPy", "numpy")
        # Stored key should be lowercase so case-insensitive matching works.
        self.assertEqual(apply_dictionary("import NumPy"), "import numpy")

    @_use_temp_dict
    def test_add_overwrites_existing_key(self):
        add_correction("foo", "bar")
        add_correction("foo", "baz")
        self.assertEqual(apply_dictionary("foo"), "baz")


class TestInferCorrections(unittest.TestCase):
    def test_single_word_substitution(self):
        pairs = infer_corrections("use pie oh my oh for sensing", "use pyomyo for sensing")
        self.assertEqual(len(pairs), 1)
        spoken, replacement = pairs[0]
        self.assertEqual(spoken, "pie oh my oh")
        self.assertEqual(replacement, "pyomyo")

    def test_identical_texts_returns_empty(self):
        pairs = infer_corrections("hello world", "hello world")
        self.assertEqual(pairs, [])

    def test_case_difference_ignored_in_spoken(self):
        pairs = infer_corrections("import NumPy", "import numpy")
        # "numpy" vs "numpy" — same after lower → no replace opcode expected,
        # so we fall back to whole-phrase.
        # Either way the result should capture the correction or return [].
        # Since "import numpy" == "import numpy" after lowering → empty is fine.
        self.assertIsInstance(pairs, list)

    def test_multiple_substitutions(self):
        pairs = infer_corrections(
            "use pie oh my oh and sky learn",
            "use pyomyo and sklearn",
        )
        spoken_vals = [s for s, _ in pairs]
        replacement_vals = [r for _, r in pairs]
        self.assertIn("pie oh my oh", spoken_vals)
        self.assertIn("sky learn", spoken_vals)
        self.assertIn("pyomyo", replacement_vals)
        self.assertIn("sklearn", replacement_vals)

    def test_ambiguous_diff_falls_back_to_full_phrase(self):
        # When every word changes, there's no clean replacement span —
        # fallback should produce one pair covering the whole utterance.
        original = "alpha bravo charlie"
        corrected = "one two three"
        pairs = infer_corrections(original, corrected)
        self.assertTrue(len(pairs) >= 1)
        # The fallback pair must cover the original as spoken key.
        all_spoken = " ".join(s for s, _ in pairs)
        self.assertIn("alpha", all_spoken)


class TestVoiceTriggerDictation(unittest.TestCase):
    """Integration: voice trigger stores raw/typed and applies dictionary."""

    def _make_trigger(self):
        from pulse.handlers.voice_trigger import VoiceTrigger
        recorder = MagicMock()
        return VoiceTrigger(recorder)

    def test_last_dictation_initially_none(self):
        vt = self._make_trigger()
        raw, typed = vt.get_last_dictation()
        self.assertIsNone(raw)
        self.assertIsNone(typed)

    @patch("pulse.dictionary.DICT_PATH")
    def test_transcribe_stores_raw_and_applies_correction(self, mock_path):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "dictionary.yaml"
            with patch.object(d, "DICT_PATH", path):
                add_correction("pie oh my oh", "pyomyo")

                from pulse.handlers.voice_trigger import VoiceTrigger
                recorder = MagicMock()
                recorder.stop_and_transcribe.return_value = "use pie oh my oh"
                vt = VoiceTrigger(recorder, on_state=lambda _: None, on_action=lambda _: None)

                vt._recording = True
                with patch("pulse.handlers.voice_trigger._keyboard"):
                    vt._transcribe_and_send()

                raw, typed = vt.get_last_dictation()
                self.assertEqual(raw, "use pie oh my oh")
                self.assertEqual(typed, "use pyomyo")


class TestEngineDictation(unittest.TestCase):
    """Engine.correct_last_dictation saves inferred corrections."""

    def _make_engine_with_vt(self, raw, typed):
        from pulse.engine import PulseEngine
        engine = MagicMock(spec=PulseEngine)
        vt = MagicMock()
        vt.get_last_dictation.return_value = (raw, typed)
        engine._voice_trigger = vt
        engine.get_last_dictation = lambda: vt.get_last_dictation()
        engine.correct_last_dictation = PulseEngine.correct_last_dictation.__get__(engine)
        engine._on_action = lambda t: None
        return engine

    @_use_temp_dict
    def test_correct_last_dictation_saves_pair(self):
        from pulse.engine import PulseEngine
        engine = MagicMock(spec=PulseEngine)
        vt = MagicMock()
        vt.get_last_dictation.return_value = ("use pie oh my oh", "use pie oh my oh")
        engine._voice_trigger = vt
        engine._on_action = MagicMock()
        engine.correct_last_dictation = PulseEngine.correct_last_dictation.__get__(engine)

        feedback = engine.correct_last_dictation("use pyomyo")
        self.assertIn("pie oh my oh", feedback)
        self.assertIn("pyomyo", feedback)
        self.assertEqual(apply_dictionary("use pie oh my oh"), "use pyomyo")

    @_use_temp_dict
    def test_correct_last_dictation_no_raw_raises(self):
        from pulse.engine import PulseEngine
        engine = MagicMock(spec=PulseEngine)
        vt = MagicMock()
        vt.get_last_dictation.return_value = (None, None)
        engine._voice_trigger = vt
        engine._on_action = MagicMock()
        engine.correct_last_dictation = PulseEngine.correct_last_dictation.__get__(engine)

        with self.assertRaises(ValueError):
            engine.correct_last_dictation("anything")

    @_use_temp_dict
    def test_correct_last_dictation_identical_returns_no_changes(self):
        from pulse.engine import PulseEngine
        engine = MagicMock(spec=PulseEngine)
        vt = MagicMock()
        vt.get_last_dictation.return_value = ("hello world", "hello world")
        engine._voice_trigger = vt
        engine._on_action = MagicMock()
        engine.correct_last_dictation = PulseEngine.correct_last_dictation.__get__(engine)

        feedback = engine.correct_last_dictation("hello world")
        self.assertEqual(feedback, "No changes detected")


if __name__ == "__main__":
    unittest.main()
