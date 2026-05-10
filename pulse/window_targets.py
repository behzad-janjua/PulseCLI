from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

TARGETS_PATH = Path(".pulse_targets.yaml")

logger = logging.getLogger(__name__)

_current_target: str | None = None


@dataclass
class WindowTarget:
    app: str
    title: str


def _run_script(script: str, timeout: float = 2.0) -> str:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_frontmost_window() -> WindowTarget | None:
    script = (
        'tell application "System Events"\n'
        '    set frontApp to first application process whose frontmost is true\n'
        '    set appName to name of frontApp\n'
        '    set winTitle to ""\n'
        '    try\n'
        '        set winTitle to name of front window of frontApp\n'
        '    end try\n'
        '    return appName & "|||" & winTitle\n'
        'end tell'
    )
    raw = _run_script(script)
    if not raw or "|||" not in raw:
        return None
    parts = raw.split("|||", 1)
    app = parts[0].strip()
    title = parts[1].strip()
    return WindowTarget(app=app, title=title) if app else None


def _esc(s: str) -> str:
    """Strip characters that would break AppleScript string literals."""
    return s.replace('"', "").replace("\\", "")


def _load_raw() -> dict[str, dict]:
    if not TARGETS_PATH.exists():
        return {}
    try:
        with TARGETS_PATH.open() as f:
            data = yaml.safe_load(f) or {}
        return data.get("targets", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_raw(targets: dict[str, dict]) -> None:
    with TARGETS_PATH.open("w") as f:
        yaml.dump({"targets": targets}, f, default_flow_style=False)


def save_target(name: str, window: WindowTarget | None = None) -> bool:
    """Save the given (or current frontmost) window under *name*."""
    if window is None:
        window = get_frontmost_window()
    if window is None:
        logger.warning("save_target: could not determine frontmost window")
        return False
    targets = _load_raw()
    targets[name] = {"app": window.app, "title": window.title}
    _save_raw(targets)
    logger.info("Saved target '%s': %s / %s", name, window.app, window.title)
    return True


def focus_target(name: str) -> bool:
    """Raise the window saved under *name*. Returns False if not found."""
    global _current_target
    targets = _load_raw()
    entry = targets.get(name)
    if not entry:
        logger.warning("focus_target: '%s' not found in %s", name, TARGETS_PATH)
        return False
    app = _esc(entry.get("app", ""))
    title = _esc(entry.get("title", ""))
    if not app:
        return False
    if title:
        script = (
            f'tell application "System Events"\n'
            f'    tell process "{app}"\n'
            f'        set frontmost to true\n'
            f'        try\n'
            f'            set w to first window whose name contains "{title}"\n'
            f'            perform action "AXRaise" of w\n'
            f'        end try\n'
            f'    end tell\n'
            f'end tell'
        )
    else:
        script = (
            f'tell application "System Events"\n'
            f'    tell process "{app}"\n'
            f'        set frontmost to true\n'
            f'    end tell\n'
            f'end tell'
        )
    _run_script(script)
    _current_target = name
    return True


def delete_target(name: str) -> bool:
    """Remove a saved target. Returns False if it did not exist."""
    global _current_target
    targets = _load_raw()
    if name not in targets:
        return False
    del targets[name]
    _save_raw(targets)
    if _current_target == name:
        _current_target = None
    return True


def list_targets() -> dict[str, WindowTarget]:
    """Return all saved targets."""
    raw = _load_raw()
    result: dict[str, WindowTarget] = {}
    for name, entry in raw.items():
        if isinstance(entry, dict) and "app" in entry:
            result[name] = WindowTarget(app=entry["app"], title=entry.get("title", ""))
    return result


def next_target() -> str | None:
    """Focus the next saved target cyclically. Returns the target name."""
    global _current_target
    keys = list(_load_raw().keys())
    if not keys:
        return None
    if _current_target is None or _current_target not in keys:
        name = keys[0]
    else:
        name = keys[(keys.index(_current_target) + 1) % len(keys)]
    focus_target(name)
    return name


def previous_target() -> str | None:
    """Focus the previous saved target cyclically. Returns the target name."""
    global _current_target
    keys = list(_load_raw().keys())
    if not keys:
        return None
    if _current_target is None or _current_target not in keys:
        name = keys[-1]
    else:
        name = keys[(keys.index(_current_target) - 1) % len(keys)]
    focus_target(name)
    return name
