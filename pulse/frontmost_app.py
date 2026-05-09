from __future__ import annotations

import subprocess


def get_frontmost_app() -> str:
    """Return the bundle name of the frontmost macOS application, or 'default' on failure."""
    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=1.0,
        )
        name = result.stdout.strip()
        return name if name else "default"
    except Exception:
        return "default"
