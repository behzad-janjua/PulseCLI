from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path("pulse.yaml")

VALID_ACTIONS = {
    "dictate", "key", "type", "shell",
    "save_target", "focus_target", "next_target", "previous_target", "pick_target",
    "set_focus_set",
    "context_type", "context_dictate",
}


class ConfigError(ValueError):
    pass


@dataclass
class ActionConfig:
    type: str
    keys: list[str] = field(default_factory=list)
    text: str = ""
    command: str = ""
    target: str = ""


@dataclass
class SequenceConfig:
    gestures: list[str]
    action: ActionConfig


@dataclass
class PulseConfig:
    profiles: dict[str, dict[str, ActionConfig]]
    sequences: list[SequenceConfig]
    focus_sets: dict[str, list[str]] = field(default_factory=dict)


def _parse_action(raw: Any, context: str) -> ActionConfig:
    if isinstance(raw, str):
        if raw not in VALID_ACTIONS:
            raise ConfigError(
                f"{context}: unknown action '{raw}'. Valid: {sorted(VALID_ACTIONS)}"
            )
        return ActionConfig(type=raw)

    if not isinstance(raw, dict):
        raise ConfigError(
            f"{context}: binding must be a string or dict, got {type(raw).__name__}"
        )

    action_type = raw.get("action")
    if not action_type:
        raise ConfigError(f"{context}: missing 'action' key")
    if action_type not in VALID_ACTIONS:
        raise ConfigError(
            f"{context}: unknown action '{action_type}'. Valid: {sorted(VALID_ACTIONS)}"
        )

    if action_type in {"save_target", "focus_target"} and not raw.get("target"):
        raise ConfigError(f"{context}: '{action_type}' requires a 'target' field")

    return ActionConfig(
        type=action_type,
        keys=raw.get("keys", []),
        text=raw.get("text", ""),
        command=raw.get("command", ""),
        target=raw.get("target", ""),
    )


def _parse_profile(raw: dict, name: str) -> dict[str, ActionConfig]:
    return {
        gesture: _parse_action(binding, f"profiles.{name}.{gesture}")
        for gesture, binding in raw.items()
    }


def _parse_sequence(raw: dict, idx: int) -> SequenceConfig:
    context = f"sequences[{idx}]"
    gestures = raw.get("gestures")
    if not gestures or not isinstance(gestures, list):
        raise ConfigError(f"{context}: 'gestures' must be a non-empty list")
    if len(gestures) < 2:
        raise ConfigError(f"{context}: sequences must have at least 2 gestures")

    action_raw = raw.get("action")
    if action_raw is None:
        raise ConfigError(f"{context}: missing 'action'")

    return SequenceConfig(
        gestures=[str(g) for g in gestures],
        action=_parse_action(action_raw, f"{context}.action"),
    )


def load_config(path: Path = CONFIG_PATH) -> PulseConfig | None:
    if not path.exists():
        return None

    with path.open() as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigError("pulse.yaml must be a YAML mapping")

    profiles_raw = raw.get("profiles", {})
    if not isinstance(profiles_raw, dict):
        raise ConfigError("'profiles' must be a mapping")

    profiles = {
        name: _parse_profile(bindings, name)
        for name, bindings in profiles_raw.items()
        if isinstance(bindings, dict)
    }

    sequences_raw = raw.get("sequences", [])
    if not isinstance(sequences_raw, list):
        raise ConfigError("'sequences' must be a list")

    sequences = [_parse_sequence(s, i) for i, s in enumerate(sequences_raw)]

    focus_sets_raw = raw.get("focus_sets", {})
    if not isinstance(focus_sets_raw, dict):
        raise ConfigError("'focus_sets' must be a mapping")
    focus_sets: dict[str, list[str]] = {}
    for set_name, members in focus_sets_raw.items():
        if not isinstance(members, list):
            raise ConfigError(f"focus_sets.{set_name}: value must be a list of target names")
        focus_sets[set_name] = [str(m) for m in members]

    return PulseConfig(profiles=profiles, sequences=sequences, focus_sets=focus_sets)
