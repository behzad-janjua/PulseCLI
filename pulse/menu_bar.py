from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import rumps

if TYPE_CHECKING:
    from pulse.engine import PulseEngine

_STATE_LABEL: dict[str, str] = {
    "disconnected": "Waiting for Myo…",
    "connected":    "Ready",
    "recording":    "Recording…",
    "transcribing": "Transcribing…",
}

_MAX_ACTION_LEN = 42


def _truncate(text: str) -> str:
    return text if len(text) <= _MAX_ACTION_LEN else text[:_MAX_ACTION_LEN - 1] + "…"


class PulseApp(rumps.App):
    def __init__(self, engine: PulseEngine) -> None:
        super().__init__("Pulse", quit_button=None)

        self._status_item = rumps.MenuItem(_STATE_LABEL["disconnected"])
        self._action_item = rumps.MenuItem("No gesture yet")

        self.menu = [
            self._status_item,
            rumps.separator,
            self._action_item,
            rumps.separator,
            rumps.MenuItem("Quit", callback=self._quit),
        ]

        self._engine = engine
        self._state  = "disconnected"
        self._action: str | None = None
        self._lock   = threading.Lock()

        engine.on_state_change(self._queue_state)
        engine.on_action(self._queue_action)

        self._timer = rumps.Timer(self._tick, 0.2)
        self._timer.start()

    def _queue_state(self, state: str) -> None:
        with self._lock:
            self._state = state

    def _queue_action(self, text: str) -> None:
        with self._lock:
            self._action = text

    def _tick(self, _) -> None:
        with self._lock:
            state  = self._state
            action = self._action

        self._status_item.title = _STATE_LABEL.get(state, state.title())

        if action is not None:
            self._action_item.title = f"↩  “{_truncate(action)}”"

    def _quit(self, _) -> None:
        self._engine.stop()
        rumps.quit_application()
