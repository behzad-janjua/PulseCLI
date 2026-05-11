from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import rumps

from pulse.window_targets import (
    WindowTarget,
    delete_target,
    focus_target,
    get_frontmost_window,
    list_targets,
    save_target,
)

if TYPE_CHECKING:
    from pulse.engine import PulseEngine

_STATE_LABEL: dict[str, str] = {
    "disconnected": "Waiting for Myo…",
    "connecting":   "Connecting…",
    "connected":    "Ready",
    "recording":    "Recording…",
    "transcribing": "Transcribing…",
    "retraining":   "Retraining model…",
}

_MAX_ACTION_LEN = 42


def _truncate(text: str) -> str:
    return text if len(text) <= _MAX_ACTION_LEN else text[:_MAX_ACTION_LEN - 1] + "…"


class PulseApp(rumps.App):
    def __init__(self, engine: PulseEngine) -> None:
        super().__init__("Pulse", quit_button=None)

        self._status_item = rumps.MenuItem(_STATE_LABEL["disconnected"])
        self._gesture_item = rumps.MenuItem("Last gesture: none")
        self._action_item = rumps.MenuItem("No gesture yet")

        self._save_window_item = rumps.MenuItem(
            "Save Current Window As…", callback=self._save_window_as
        )
        self._targets_item = rumps.MenuItem("Window Targets")
        self._no_targets_item = rumps.MenuItem("(none saved)")
        self._targets_item.update([self._no_targets_item])

        self.menu = [
            self._status_item,
            rumps.separator,
            self._gesture_item,
            self._action_item,
            rumps.separator,
            rumps.MenuItem("Teach New Gesture…", callback=self._teach_gesture),
            rumps.MenuItem("Correct Last Gesture…", callback=self._correct_last_gesture),
            rumps.MenuItem("Retrain Model", callback=self._retrain_model),
            rumps.separator,
            self._save_window_item,
            self._targets_item,
            rumps.separator,
            rumps.MenuItem("Quit", callback=self._quit),
        ]

        self._engine = engine
        self._state  = "disconnected"
        self._action: str | None = None
        self._gesture: str | None = None
        self._lock   = threading.Lock()

        self._snapshot_window: WindowTarget | None = None
        self._tick_count = 0

        engine.on_state_change(self._queue_state)
        engine.on_action(self._queue_action)
        engine.on_gesture(self._queue_gesture)

        self._timer = rumps.Timer(self._tick, 0.2)
        self._timer.start()

    def _queue_state(self, state: str) -> None:
        with self._lock:
            self._state = state

    def _queue_action(self, text: str) -> None:
        with self._lock:
            self._action = text

    def _queue_gesture(self, gesture: str) -> None:
        with self._lock:
            self._gesture = gesture

    _SNAPSHOT_EXCLUDED = {"Python", "python3", "python", "Pulse"}

    def _tick(self, _) -> None:
        with self._lock:
            state  = self._state
            action = self._action
            gesture = self._gesture

        self._status_item.title = _STATE_LABEL.get(state, state.title())
        if gesture is not None:
            self._gesture_item.title = f"Last gesture: {_truncate(gesture)}"
        if action is not None:
            self._action_item.title = f'↩  "{_truncate(action)}"'

        self._tick_count += 1
        if self._tick_count % 5 == 0:
            self._refresh_snapshot()
            self._refresh_targets_menu()

    def _refresh_snapshot(self) -> None:
        try:
            w = get_frontmost_window()
            if w and w.app not in self._SNAPSHOT_EXCLUDED:
                self._snapshot_window = w
        except Exception:
            pass

    def _refresh_targets_menu(self) -> None:
        targets = list_targets()
        self._targets_item.clear()
        if not targets:
            self._targets_item.update([self._no_targets_item])
            return
        items = []
        for name, wt in targets.items():
            label = f"{name}  ({wt.app})"
            submenu = rumps.MenuItem(label)
            submenu.update([
                rumps.MenuItem("Focus", callback=self._make_focus_cb(name)),
                rumps.MenuItem("Delete", callback=self._make_delete_cb(name)),
            ])
            items.append(submenu)
        self._targets_item.update(items)

    def _make_focus_cb(self, name: str):
        def _cb(_):
            ok = focus_target(name)
            if not ok:
                rumps.alert(f"Target '{name}' not found.\nIt may have been closed.", ok="OK")
        return _cb

    def _make_delete_cb(self, name: str):
        def _cb(_):
            ok = delete_target(name)
            if ok:
                self._queue_action(f"Deleted target: {name}")
            else:
                rumps.alert(f"Target '{name}' not found.", ok="OK")
        return _cb

    def _save_window_as(self, _) -> None:
        window = self._snapshot_window
        if window is None:
            rumps.alert(
                "No window captured yet.\n\nTip: use a gesture with action: save_target so Pulse can capture the window before the menu opens.",
                ok="OK",
            )
            return
        hint = f"{window.app} — {window.title}" if window.title else window.app
        response = rumps.Window(
            message=f"Saving: {hint}\n\nEnter a name for this target:",
            title="Save Current Window As…",
            default_text="",
            ok="Save",
            cancel="Cancel",
        ).run()
        if not response.clicked:
            return
        name = response.text.strip()
        if not name:
            return
        ok = save_target(name, window)
        if ok:
            self._queue_action(f"Saved target: {name}")
        else:
            rumps.alert(f"Could not save target '{name}'.", ok="OK")

    def _teach_gesture(self, _) -> None:
        label = self._prompt_label(
            "Teach New Gesture",
            "Hold your gesture, then enter a name for it.",
        )
        if not label:
            return
        self._run_learning_task(
            lambda: self._engine.teach_gesture(label),
            "Saving teaching samples…",
        )

    def _correct_last_gesture(self, _) -> None:
        last = self._engine.get_last_gesture() or ""
        label = self._prompt_label(
            "Correct Last Gesture",
            f"Last gesture was '{last}'. Enter the correct label.",
            default_text=last,
        )
        if not label:
            return
        self._run_learning_task(
            lambda: self._engine.correct_last_gesture(label),
            "Saving correction…",
        )

    def _retrain_model(self, _) -> None:
        self._run_learning_task(self._engine.retrain_model, "Retraining model…")

    def _prompt_label(
        self,
        title: str,
        message: str,
        default_text: str = "",
    ) -> str | None:
        response = rumps.Window(
            message=message,
            title=title,
            default_text=default_text,
            ok="Save",
            cancel="Cancel",
        ).run()
        if not response.clicked:
            return None
        label = response.text.strip()
        return label or None

    def _run_learning_task(self, task, pending: str) -> None:
        self._queue_action(pending)

        def worker() -> None:
            try:
                task()
            except Exception as exc:
                self._queue_action(f"Learning error: {exc}")

        threading.Thread(target=worker, daemon=True, name="pulse-learning").start()

    def _quit(self, _) -> None:
        self._engine.stop()
        rumps.quit_application()
