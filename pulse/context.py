from __future__ import annotations

import subprocess
from pathlib import Path


def gather() -> str:
    """Return a short context string to append to dictated text."""
    parts: list[str] = []
    parts.append(f"cwd:{Path.cwd().name}")

    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if branch:
            parts.append(f"branch:{branch}")
            dirty = subprocess.check_output(
                ["git", "status", "--porcelain"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            if dirty:
                parts.append("uncommitted changes")
    except Exception:
        pass

    return " | ".join(parts)
