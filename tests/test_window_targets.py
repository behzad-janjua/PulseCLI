from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pulse.window_targets as wt
from pulse.window_targets import (
    WindowTarget,
    delete_target,
    focus_target,
    list_targets,
    next_target,
    previous_target,
    save_target,
)


def _use_temp_targets(test_fn):
    """Decorator: run test with an isolated targets file and reset module state."""
    def wrapper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".pulse_targets.yaml"
            with patch.object(wt, "TARGETS_PATH", path):
                wt._current_target = None
                test_fn(self)
                wt._current_target = None
    wrapper.__name__ = test_fn.__name__
    return wrapper


class TestSaveTarget(unittest.TestCase):
    @_use_temp_targets
    def test_save_returns_true_and_persists(self):
        window = WindowTarget(app="Terminal", title="zsh")
        ok = save_target("term", window)
        self.assertTrue(ok)
        targets = list_targets()
        self.assertIn("term", targets)
        self.assertEqual(targets["term"].app, "Terminal")
        self.assertEqual(targets["term"].title, "zsh")

    @_use_temp_targets
    def test_save_without_explicit_window_calls_get_frontmost(self):
        with patch.object(wt, "get_frontmost_window",
                          return_value=WindowTarget(app="Code", title="main.py")):
            ok = save_target("editor")
        self.assertTrue(ok)
        self.assertEqual(list_targets()["editor"].app, "Code")

    @_use_temp_targets
    def test_save_fails_when_no_window(self):
        with patch.object(wt, "get_frontmost_window", return_value=None):
            ok = save_target("ghost")
        self.assertFalse(ok)
        self.assertEqual(list_targets(), {})

    @_use_temp_targets
    def test_save_overwrites_existing(self):
        save_target("x", WindowTarget(app="A", title="1"))
        save_target("x", WindowTarget(app="B", title="2"))
        self.assertEqual(list_targets()["x"].app, "B")


class TestFocusTarget(unittest.TestCase):
    @_use_temp_targets
    def test_focus_missing_returns_false(self):
        ok = focus_target("nonexistent")
        self.assertFalse(ok)

    @_use_temp_targets
    def test_focus_existing_calls_applescript(self):
        save_target("left", WindowTarget(app="claude", title="left"))
        with patch.object(wt, "_run_script", return_value="") as mock_script:
            ok = focus_target("left")
        self.assertTrue(ok)
        mock_script.assert_called_once()
        self.assertIn("claude", mock_script.call_args[0][0])

    @_use_temp_targets
    def test_focus_updates_current_target(self):
        save_target("right", WindowTarget(app="claude", title="right"))
        with patch.object(wt, "_run_script", return_value=""):
            focus_target("right")
        self.assertEqual(wt._current_target, "right")

    @_use_temp_targets
    def test_focus_target_no_title_omits_window_clause(self):
        save_target("bare", WindowTarget(app="Finder", title=""))
        with patch.object(wt, "_run_script", return_value="") as mock_script:
            focus_target("bare")
        script = mock_script.call_args[0][0]
        self.assertNotIn("first window", script)


class TestDeleteTarget(unittest.TestCase):
    @_use_temp_targets
    def test_delete_existing(self):
        save_target("a", WindowTarget(app="X", title=""))
        ok = delete_target("a")
        self.assertTrue(ok)
        self.assertNotIn("a", list_targets())

    @_use_temp_targets
    def test_delete_nonexistent_returns_false(self):
        ok = delete_target("nope")
        self.assertFalse(ok)

    @_use_temp_targets
    def test_delete_clears_current_target(self):
        save_target("c", WindowTarget(app="X", title=""))
        with patch.object(wt, "_run_script", return_value=""):
            focus_target("c")
        delete_target("c")
        self.assertIsNone(wt._current_target)


class TestNextPreviousTarget(unittest.TestCase):
    @_use_temp_targets
    def test_next_returns_none_when_empty(self):
        result = next_target()
        self.assertIsNone(result)

    @_use_temp_targets
    def test_next_cycles_forward(self):
        save_target("a", WindowTarget(app="A", title=""))
        save_target("b", WindowTarget(app="B", title=""))
        save_target("c", WindowTarget(app="C", title=""))

        with patch.object(wt, "_run_script", return_value=""):
            n1 = next_target()
            n2 = next_target()
            n3 = next_target()
            n4 = next_target()

        self.assertEqual(n1, "a")
        self.assertEqual(n2, "b")
        self.assertEqual(n3, "c")
        self.assertEqual(n4, "a")  # wraps

    @_use_temp_targets
    def test_previous_cycles_backward(self):
        save_target("a", WindowTarget(app="A", title=""))
        save_target("b", WindowTarget(app="B", title=""))

        with patch.object(wt, "_run_script", return_value=""):
            p1 = previous_target()
            p2 = previous_target()

        self.assertEqual(p1, "b")  # starts at end
        self.assertEqual(p2, "a")

    @_use_temp_targets
    def test_next_from_unknown_starts_at_first(self):
        save_target("x", WindowTarget(app="X", title=""))
        wt._current_target = "does_not_exist"
        with patch.object(wt, "_run_script", return_value=""):
            n = next_target()
        self.assertEqual(n, "x")


if __name__ == "__main__":
    unittest.main()
