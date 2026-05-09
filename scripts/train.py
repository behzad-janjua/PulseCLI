"""
Train a personal gesture classifier from collected EMG data.

Usage:
    .venv/bin/python3 scripts/train.py

Reads from data/raw/, trains a Random Forest, saves to models/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pulse.training import DATA_DIR, MODEL_DIR, train_classifier


def train() -> None:
    print("=== PulseCLI Gesture Classifier Training ===\n")
    try:
        train_classifier(DATA_DIR, MODEL_DIR, verbose=True)
    except ValueError as exc:
        print(exc)
        print("Run `make collect` first.")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    train()
