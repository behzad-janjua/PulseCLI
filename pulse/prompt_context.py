from __future__ import annotations

import subprocess
from pathlib import Path

from pulse.frontmost_app import get_frontmost_app


def _git_info() -> dict[str, object]:
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if not branch:
            return {}
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        )
        return {"branch": branch, "uncommitted_changes": dirty}
    except Exception:
        return {}


def gather_context(target: str | None = None) -> dict[str, object]:
    """Return a dict of local context fields for prompt annotation."""
    ctx: dict[str, object] = {
        "cwd": Path.cwd().name,
        "app": get_frontmost_app(),
    }
    ctx.update(_git_info())
    if target:
        ctx["target"] = target
    return ctx


def compose_prompt(text: str, target: str | None = None) -> str:
    """Append a Context block to *text* using local environment info."""
    ctx = gather_context(target)

    lines = [text, "", "Context:"]
    if "target" in ctx:
        lines.append(f"- target: {ctx['target']}")
    lines.append(f"- app: {ctx['app']}")
    lines.append(f"- cwd: {ctx['cwd']}")
    if "branch" in ctx:
        lines.append(f"- branch: {ctx['branch']}")
    if ctx.get("uncommitted_changes"):
        lines.append("- uncommitted changes: yes")

    return "\n".join(lines)
