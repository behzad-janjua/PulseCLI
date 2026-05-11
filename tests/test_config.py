import textwrap
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

from pulse.config import ConfigError, load_config


def _write_yaml(content: str) -> Path:
    f = NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(textwrap.dedent(content))
    f.close()
    return Path(f.name)


class TestLoadConfig(unittest.TestCase):
    def test_returns_none_when_file_missing(self):
        self.assertIsNone(load_config(Path("/nonexistent/pulse.yaml")))

    def test_minimal_config(self):
        p = _write_yaml("""
            profiles:
              default:
                fist: dictate
        """)
        cfg = load_config(p)
        self.assertIsNotNone(cfg)
        action = cfg.profiles["default"]["fist"]
        self.assertEqual(action.type, "dictate")
        p.unlink()

    def test_key_action(self):
        p = _write_yaml("""
            profiles:
              default:
                wave_out:
                  action: key
                  keys: [cmd, tab]
        """)
        cfg = load_config(p)
        action = cfg.profiles["default"]["wave_out"]
        self.assertEqual(action.type, "key")
        self.assertEqual(action.keys, ["cmd", "tab"])
        p.unlink()

    def test_type_action(self):
        p = _write_yaml("""
            profiles:
              default:
                fist:
                  action: type
                  text: "hello world"
        """)
        cfg = load_config(p)
        action = cfg.profiles["default"]["fist"]
        self.assertEqual(action.type, "type")
        self.assertEqual(action.text, "hello world")
        p.unlink()

    def test_shell_action(self):
        p = _write_yaml("""
            profiles:
              default:
                fist:
                  action: shell
                  command: "echo hi"
        """)
        cfg = load_config(p)
        action = cfg.profiles["default"]["fist"]
        self.assertEqual(action.type, "shell")
        self.assertEqual(action.command, "echo hi")
        p.unlink()

    def test_sequence_parsed(self):
        p = _write_yaml("""
            profiles: {}
            sequences:
              - gestures: [fist, wave_out]
                action: dictate
        """)
        cfg = load_config(p)
        self.assertEqual(len(cfg.sequences), 1)
        seq = cfg.sequences[0]
        self.assertEqual(seq.gestures, ["fist", "wave_out"])
        self.assertEqual(seq.action.type, "dictate")
        p.unlink()

    def test_unknown_action_raises(self):
        p = _write_yaml("""
            profiles:
              default:
                fist: jump
        """)
        with self.assertRaises(ConfigError):
            load_config(p)
        p.unlink()

    def test_sequence_requires_two_gestures(self):
        p = _write_yaml("""
            profiles: {}
            sequences:
              - gestures: [fist]
                action: dictate
        """)
        with self.assertRaises(ConfigError):
            load_config(p)
        p.unlink()

    def test_sequence_missing_action_raises(self):
        p = _write_yaml("""
            profiles: {}
            sequences:
              - gestures: [fist, wave_out]
        """)
        with self.assertRaises(ConfigError):
            load_config(p)
        p.unlink()

    def test_focus_target_action(self):
        p = _write_yaml("""
            profiles:
              default:
                wave_out:
                  action: focus_target
                  target: claude_right
        """)
        cfg = load_config(p)
        action = cfg.profiles["default"]["wave_out"]
        self.assertEqual(action.type, "focus_target")
        self.assertEqual(action.target, "claude_right")
        p.unlink()

    def test_save_target_action(self):
        p = _write_yaml("""
            profiles:
              default:
                fist:
                  action: save_target
                  target: my_window
        """)
        cfg = load_config(p)
        action = cfg.profiles["default"]["fist"]
        self.assertEqual(action.type, "save_target")
        self.assertEqual(action.target, "my_window")
        p.unlink()

    def test_next_target_action(self):
        p = _write_yaml("""
            profiles:
              default:
                wave_out: next_target
        """)
        cfg = load_config(p)
        action = cfg.profiles["default"]["wave_out"]
        self.assertEqual(action.type, "next_target")
        p.unlink()

    def test_focus_target_missing_target_raises(self):
        p = _write_yaml("""
            profiles:
              default:
                wave_out:
                  action: focus_target
        """)
        with self.assertRaises(ConfigError):
            load_config(p)
        p.unlink()

    def test_focus_sets_parsed(self):
        p = _write_yaml("""
            profiles: {}
            focus_sets:
              coding:
                - Cursor
                - Terminal
                - claude_left
        """)
        cfg = load_config(p)
        self.assertEqual(cfg.focus_sets, {"coding": ["Cursor", "Terminal", "claude_left"]})
        p.unlink()

    def test_focus_sets_defaults_to_empty(self):
        p = _write_yaml("""
            profiles:
              default:
                fist: dictate
        """)
        cfg = load_config(p)
        self.assertEqual(cfg.focus_sets, {})
        p.unlink()

    def test_focus_sets_invalid_raises(self):
        p = _write_yaml("""
            profiles: {}
            focus_sets:
              coding: not_a_list
        """)
        with self.assertRaises(ConfigError):
            load_config(p)
        p.unlink()

    def test_set_focus_set_action(self):
        p = _write_yaml("""
            profiles:
              default:
                wave_out:
                  action: set_focus_set
                  target: coding
        """)
        cfg = load_config(p)
        action = cfg.profiles["default"]["wave_out"]
        self.assertEqual(action.type, "set_focus_set")
        self.assertEqual(action.target, "coding")
        p.unlink()


if __name__ == "__main__":
    unittest.main()
