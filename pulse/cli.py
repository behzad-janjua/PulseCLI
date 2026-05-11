from __future__ import annotations

import argparse
import subprocess
import sys
import warnings
from pathlib import Path

_SCRIPTS = Path(__file__).parent.parent / "scripts"


def _engine_run(*, discover: bool = False, use_custom: bool = False) -> None:
    warnings.filterwarnings(
        "ignore",
        message="resource_tracker: There appear to be",
        category=UserWarning,
    )
    from pulse.engine import PulseEngine
    engine = PulseEngine(discover=discover, use_custom=use_custom)
    if discover:
        engine.run_blocking()
        return
    from pulse.menu_bar import PulseApp
    app = PulseApp(engine)
    engine.start()
    app.run()


def _collect(add: str | None) -> None:
    cmd = [sys.executable, str(_SCRIPTS / "collect.py")]
    if add:
        cmd += ["--add", add]
    sys.exit(subprocess.call(cmd))


def _train() -> None:
    from pulse.training import DATA_DIR, MODEL_DIR, train_classifier
    print("Training gesture classifier...\n")
    try:
        train_classifier(DATA_DIR, MODEL_DIR, verbose=True)
    except ValueError as exc:
        print(f"Error: {exc}\nRun `pulse collect` first.", file=sys.stderr)
        sys.exit(1)


def _targets_list() -> None:
    from pulse.window_targets import list_targets
    targets = list_targets()
    if not targets:
        print("No targets saved.")
        return
    for name, wt in targets.items():
        suffix = f"  {wt.title}" if wt.title else ""
        print(f"  {name:<20} {wt.app}{suffix}")


def _targets_save(name: str) -> None:
    from pulse.window_targets import save_target
    if save_target(name):
        print(f"Saved '{name}'.")
    else:
        print("Could not read frontmost window.", file=sys.stderr)
        sys.exit(1)


def _targets_focus(name: str) -> None:
    from pulse.window_targets import focus_target
    if not focus_target(name):
        print(f"Target '{name}' not found.", file=sys.stderr)
        sys.exit(1)


def _targets_delete(name: str) -> None:
    from pulse.window_targets import delete_target
    if delete_target(name):
        print(f"Deleted '{name}'.")
    else:
        print(f"Target '{name}' not found.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pulse",
        description="PulseCLI — gesture + voice layer for AI-assisted dev",
    )
    sub = parser.add_subparsers(dest="cmd", metavar="command")
    sub.required = True

    sub.add_parser("run",      help="start Pulse with the hardware classifier")
    sub.add_parser("custom",   help="start Pulse with your personal trained classifier")
    sub.add_parser("discover", help="print raw MYO pose values (debug)")
    sub.add_parser("app",      help="alias for 'run'")

    p_collect = sub.add_parser("collect", help="collect EMG training data")
    p_collect.add_argument("--add", metavar="GESTURE", help="collect data for one new gesture")

    sub.add_parser("train", help="train the personal gesture classifier")

    p_targets = sub.add_parser("targets", help="manage saved window targets")
    tsub = p_targets.add_subparsers(dest="targets_cmd", metavar="subcommand")
    tsub.required = True
    tsub.add_parser("list",   help="list all saved targets")
    tsub.add_parser("save",   help="save the frontmost window").add_argument("name")
    tsub.add_parser("focus",  help="raise a saved target window").add_argument("name")
    tsub.add_parser("delete", help="remove a saved target").add_argument("name")

    args = parser.parse_args()

    match args.cmd:
        case "run" | "app":
            _engine_run()
        case "custom":
            _engine_run(use_custom=True)
        case "discover":
            _engine_run(discover=True)
        case "collect":
            _collect(add=getattr(args, "add", None))
        case "train":
            _train()
        case "targets":
            match args.targets_cmd:
                case "list":
                    _targets_list()
                case "save":
                    _targets_save(args.name)
                case "focus":
                    _targets_focus(args.name)
                case "delete":
                    _targets_delete(args.name)


if __name__ == "__main__":
    main()
