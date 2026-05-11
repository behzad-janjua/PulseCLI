from __future__ import annotations

import logging
import subprocess
import threading
from typing import TYPE_CHECKING

from pynput.keyboard import Controller, Key

from pulse.config import ActionConfig, PulseConfig, SequenceConfig
from pulse.events import GestureEvent
from pulse.frontmost_app import get_frontmost_app
from pulse.gestures import Gesture
from pulse.handlers.voice_trigger import VoiceTrigger
from pulse.window_targets import (
    focus_target as wt_focus,
    next_target as wt_next,
    previous_target as wt_previous,
    save_target as wt_save,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_keyboard = Controller()

YELLOW = "\033[33m"
GREEN  = "\033[32m"
RED    = "\033[31m"
RESET  = "\033[0m"

SEQUENCE_TIMEOUT = 1.2  # seconds


_KEY_MAP: dict[str, Key] = {
    "cmd":     Key.cmd,
    "ctrl":    Key.ctrl,
    "alt":     Key.alt,
    "shift":   Key.shift,
    "space":   Key.space,
    "enter":   Key.enter,
    "tab":     Key.tab,
    "esc":     Key.esc,
    "up":      Key.up,
    "down":    Key.down,
    "left":    Key.left,
    "right":   Key.right,
    "f1":      Key.f1,  "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
    "f5":      Key.f5,  "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
    "f9":      Key.f9,  "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
}


def _resolve_key(name: str) -> Key | str:
    lower = name.lower()
    return _KEY_MAP.get(lower, lower)


def _execute_action(action: ActionConfig, voice_trigger: VoiceTrigger) -> None:
    if action.type == "dictate":
        voice_trigger.toggle()

    elif action.type == "key":
        keys = [_resolve_key(k) for k in action.keys]
        if not keys:
            return
        held = keys[:-1]
        final = keys[-1]
        ctx_stack: list = []
        for k in held:
            ctx = _keyboard.pressed(k)
            ctx.__enter__()
            ctx_stack.append(ctx)
        _keyboard.tap(final)
        for ctx in reversed(ctx_stack):
            ctx.__exit__(None, None, None)

    elif action.type == "type":
        if action.text:
            _keyboard.type(action.text)

    elif action.type == "shell":
        if action.command:
            try:
                subprocess.Popen(
                    action.command,
                    shell=True,
                    stdout=None,
                    stderr=None,
                )
            except Exception as exc:
                print(f"{RED}[PULSE] shell error: {exc}{RESET}", flush=True)

    elif action.type == "save_target":
        if action.target:
            ok = wt_save(action.target)
            if ok:
                print(f"{GREEN}[PULSE] saved target '{action.target}'{RESET}", flush=True)
            else:
                print(f"{RED}[PULSE] save_target: could not read frontmost window{RESET}", flush=True)

    elif action.type == "focus_target":
        if action.target:
            ok = wt_focus(action.target)
            if not ok:
                print(f"{YELLOW}[PULSE] focus_target '{action.target}' not found{RESET}", flush=True)

    elif action.type == "next_target":
        name = wt_next()
        if name:
            print(f"{GREEN}[PULSE] next target → {name}{RESET}", flush=True)
        else:
            print(f"{YELLOW}[PULSE] next_target: no targets saved{RESET}", flush=True)

    elif action.type == "previous_target":
        name = wt_previous()
        if name:
            print(f"{GREEN}[PULSE] previous target → {name}{RESET}", flush=True)
        else:
            print(f"{YELLOW}[PULSE] previous_target: no targets saved{RESET}", flush=True)

    elif action.type == "context_type":
        from pulse.prompt_context import compose_prompt
        prompt = compose_prompt(action.text, action.target or None)
        _keyboard.type(prompt)

    elif action.type == "context_dictate":
        voice_trigger.toggle_with_context(action.target or None)


class RecipeHandler:
    def __init__(self, config: PulseConfig, voice_trigger: VoiceTrigger) -> None:
        self._config = config
        self._voice_trigger = voice_trigger
        self._seq_buffer: list[str] = []
        self._seq_timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def __call__(self, event: GestureEvent) -> None:
        gesture_name = _gesture_name(event)
        if gesture_name is None:
            return

        with self._lock:
            self._seq_buffer.append(gesture_name)
            current = list(self._seq_buffer)

        if self._seq_timer:
            self._seq_timer.cancel()

        # Check if current buffer matches any sequence exactly
        matched_seq = self._find_sequence(current)
        if matched_seq:
            self._commit_sequence(matched_seq)
            return

        # Check if any sequence could still extend from current buffer
        if self._has_sequence_prefix(current):
            # Wait for more gestures
            self._seq_timer = threading.Timer(
                SEQUENCE_TIMEOUT, self._flush_buffer
            )
            self._seq_timer.daemon = True
            self._seq_timer.start()
        else:
            self._flush_buffer()

    def _find_sequence(self, gestures: list[str]) -> SequenceConfig | None:
        for seq in self._config.sequences:
            if seq.gestures == gestures:
                return seq
        return None

    def _has_sequence_prefix(self, gestures: list[str]) -> bool:
        for seq in self._config.sequences:
            if seq.gestures[: len(gestures)] == gestures and len(seq.gestures) > len(gestures):
                return True
        return False

    def _flush_buffer(self) -> None:
        with self._lock:
            gestures = list(self._seq_buffer)
            self._seq_buffer.clear()

        if not gestures:
            return

        # Execute each gesture individually as single-gesture actions
        for gesture_name in gestures:
            self._dispatch_single(gesture_name)

    def _commit_sequence(self, seq: SequenceConfig) -> None:
        with self._lock:
            self._seq_buffer.clear()
        if self._seq_timer:
            self._seq_timer.cancel()
            self._seq_timer = None

        print(
            f"{GREEN}[PULSE] sequence {'+'.join(seq.gestures)}{RESET}", flush=True
        )
        _execute_action(seq.action, self._voice_trigger)

    def _dispatch_single(self, gesture_name: str) -> None:
        app = get_frontmost_app()
        profile = (
            self._config.profiles.get(app)
            or self._config.profiles.get("default")
            or {}
        )
        action = profile.get(gesture_name)
        if action:
            _execute_action(action, self._voice_trigger)


def _gesture_name(event: GestureEvent) -> str | None:
    if event.gesture == Gesture.UNKNOWN:
        custom_label = event.metadata.get("custom_label")
        return str(custom_label) if custom_label else None
    if event.gesture == Gesture.REST:
        return None
    return event.gesture.value
