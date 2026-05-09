"""
EMG data collection script.

Usage:
    .venv/bin/python3 scripts/collect.py              # collect all default gestures
    .venv/bin/python3 scripts/collect.py --add pinch  # add one new custom gesture
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from pyomyo import Myo, emg_mode

DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_GESTURES = ["rest", "fist", "wave_in", "wave_out", "fingers_spread"]
TRIALS_PER_GESTURE = 5
RECORD_SECONDS = 4
REST_SECONDS = 3

_buffer: list[tuple] = []


def _on_emg(emg: tuple, moving: int) -> None:
    _buffer.append(emg)


def _next_trial_index(gesture: str) -> int:
    return len(list(DATA_DIR.glob(f"{gesture}_*.npy")))


def _run_session(myo: Myo, gestures: list[str]) -> None:
    print("\n=== PulseCLI EMG Data Collection ===")
    print(f"Gestures : {', '.join(gestures)}")
    print(f"Trials   : {TRIALS_PER_GESTURE} per gesture")
    print(f"Duration : {RECORD_SECONDS}s per trial")
    print("\nPress Ctrl+C at any time to stop.\n")

    for gesture in gestures:
        print(f"\n--- {gesture.upper()} ---")
        for trial in range(TRIALS_PER_GESTURE):
            idx = _next_trial_index(gesture)
            print(f"\nTrial {trial + 1}/{TRIALS_PER_GESTURE} — get ready: {gesture}")
            for i in range(3, 0, -1):
                print(f"  {i}...")
                _flush(myo, 1.0)

            print("  GO — hold the gesture!")
            _buffer.clear()
            _flush(myo, RECORD_SECONDS)

            samples = np.array(_buffer, dtype=np.float32)
            path = DATA_DIR / f"{gesture}_{idx:03d}.npy"
            np.save(path, samples)
            print(f"  Saved {len(samples)} samples → {path.name}")

            if trial < TRIALS_PER_GESTURE - 1:
                print("  Relax...")
                _flush(myo, REST_SECONDS)


def _flush(myo: Myo, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        myo.run()


def _print_status() -> None:
    all_files = sorted(DATA_DIR.glob("*.npy"))
    if not all_files:
        print("  (no data collected yet)")
        return

    # group by gesture name
    counts: dict[str, int] = {}
    for f in all_files:
        name = f.stem.rsplit("_", 1)[0]
        counts[name] = counts.get(name, 0) + 1

    built_in = set(DEFAULT_GESTURES)
    for name, n in sorted(counts.items()):
        tag = "" if name in built_in else "  [custom]"
        print(f"  {name:<20} {n} trial(s){tag}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--add",
        metavar="GESTURE",
        help="collect data for a single new custom gesture",
    )
    args = parser.parse_args()

    print("\n=== PulseCLI — Gesture Data ===")
    print("\nCurrent gesture library:")
    _print_status()

    print("\nDefault gestures:")
    for g in DEFAULT_GESTURES:
        print(f"  {g}")

    if args.add:
        gestures = [args.add]
        print(f"\nAdding new gesture: {args.add}")
    else:
        gestures = DEFAULT_GESTURES
        print(f"\nCollecting all {len(gestures)} default gestures.")

    print(f"\n{TRIALS_PER_GESTURE} trials × {RECORD_SECONDS}s each per gesture.")
    input("\nPress Enter to start, or Ctrl+C to cancel...")

    myo = Myo(mode=emg_mode.RAW)
    try:
        myo.connect()
    except Exception as e:
        print(f"MYO connection failed: {e}\nIs the dongle plugged in?")
        sys.exit(1)

    myo.add_emg_handler(_on_emg)

    try:
        _run_session(myo, gestures)
    except KeyboardInterrupt:
        print("\nCollection stopped.")
    finally:
        myo.disconnect()
        print("MYO disconnected.")

    print("\nUpdated gesture library:")
    _print_status()
    print("\nRun `make train` to retrain with the new data.")


if __name__ == "__main__":
    main()
