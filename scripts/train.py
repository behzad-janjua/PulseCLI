"""
Train a personal gesture classifier from collected EMG data.

Usage:
    .venv/bin/python3 scripts/train.py

Reads from data/raw/, trains a Random Forest, saves to models/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder

from pulse.emg.features import extract_features

DATA_DIR  = Path(__file__).parent.parent / "data" / "raw"
MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

WINDOW_SAMPLES = 60   # ~300ms at 200Hz
STEP_SAMPLES   = 30   # 50% overlap → new window every ~150ms


def load_data() -> tuple[np.ndarray, list[str]]:
    X, y = [], []
    files = sorted(DATA_DIR.glob("*.npy"))

    if not files:
        print(f"No data found in {DATA_DIR}")
        print("Run `make collect` first.")
        raise SystemExit(1)

    for path in files:
        gesture = path.stem.rsplit("_", 1)[0]
        samples = np.load(path)                      # shape: (n_samples, 8)

        if len(samples) < WINDOW_SAMPLES:
            print(f"  Skipping {path.name} — too short ({len(samples)} samples)")
            continue

        for start in range(0, len(samples) - WINDOW_SAMPLES, STEP_SAMPLES):
            window = samples[start : start + WINDOW_SAMPLES]
            X.append(extract_features(window))
            y.append(gesture)

    print(f"Loaded {len(files)} files → {len(X)} windows")
    return np.array(X), y


def train() -> None:
    print("=== PulseCLI Gesture Classifier Training ===\n")

    X, y_labels = load_data()

    le = LabelEncoder()
    y = le.fit_transform(y_labels)

    print(f"Classes : {list(le.classes_)}")
    print(f"Samples : {len(X)}\n")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    clf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)

    scores = cross_val_score(clf, X, y, cv=5)
    print(f"CV accuracy : {scores.mean():.1%} ± {scores.std():.1%}")
    print()
    print(classification_report(y_test, clf.predict(X_test), target_names=le.classes_))

    joblib.dump(clf, MODEL_DIR / "gesture_classifier.pkl")
    joblib.dump(le,  MODEL_DIR / "label_encoder.pkl")
    print(f"Model saved to models/")


if __name__ == "__main__":
    train()
