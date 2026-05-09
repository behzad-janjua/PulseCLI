from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder

from pulse.emg.features import extract_features

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"
MODEL_DIR = PROJECT_ROOT / "models"

WINDOW_SAMPLES = 60   # ~300ms at 200Hz
STEP_SAMPLES = 30     # 50% overlap -> new window every ~150ms


@dataclass
class TrainingResult:
    classes: list[str]
    samples: int
    files: int
    cv_mean: float | None = None
    cv_std: float | None = None
    report: str = ""


def load_data(data_dir: Path = DATA_DIR) -> tuple[np.ndarray, list[str], int]:
    X, y = [], []
    files = sorted(data_dir.glob("*.npy"))

    if not files:
        raise ValueError(f"No data found in {data_dir}")

    for path in files:
        gesture = path.stem.rsplit("_", 1)[0]
        samples = np.load(path)

        if len(samples) < WINDOW_SAMPLES:
            continue

        for start in range(0, len(samples) - WINDOW_SAMPLES + 1, STEP_SAMPLES):
            window = samples[start : start + WINDOW_SAMPLES]
            X.append(extract_features(window))
            y.append(gesture)

    if not X:
        raise ValueError(f"No usable EMG windows found in {data_dir}")

    return np.array(X), y, len(files)


def train_classifier(
    data_dir: Path = DATA_DIR,
    model_dir: Path = MODEL_DIR,
    *,
    verbose: bool = True,
) -> TrainingResult:
    X, y_labels, file_count = load_data(data_dir)

    le = LabelEncoder()
    y = le.fit_transform(y_labels)

    clf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    clf.fit(X, y)

    counts = Counter(y)
    min_class_count = min(counts.values())
    cv_folds = min(5, min_class_count)
    cv_mean: float | None = None
    cv_std: float | None = None
    if len(counts) > 1 and cv_folds >= 2:
        scores = cross_val_score(clf, X, y, cv=cv_folds)
        cv_mean = float(scores.mean())
        cv_std = float(scores.std())

    report = ""
    if len(counts) > 1 and min_class_count >= 2:
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, stratify=y, random_state=42
            )
            report_clf = RandomForestClassifier(
                n_estimators=200, random_state=42, n_jobs=-1
            )
            report_clf.fit(X_train, y_train)
            report = classification_report(
                y_test,
                report_clf.predict(X_test),
                target_names=le.classes_,
                zero_division=0,
            )
        except ValueError:
            report = ""

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, model_dir / "gesture_classifier.pkl")
    joblib.dump(le, model_dir / "label_encoder.pkl")

    result = TrainingResult(
        classes=list(le.classes_),
        samples=len(X),
        files=file_count,
        cv_mean=cv_mean,
        cv_std=cv_std,
        report=report,
    )

    if verbose:
        print_training_result(result)

    return result


def print_training_result(result: TrainingResult) -> None:
    print(f"Loaded {result.files} files -> {result.samples} windows")
    print(f"Classes : {result.classes}")
    print(f"Samples : {result.samples}\n")
    if result.cv_mean is not None and result.cv_std is not None:
        print(f"CV accuracy : {result.cv_mean:.1%} +/- {result.cv_std:.1%}")
    else:
        print("CV accuracy : skipped (not enough samples per class)")
    print()
    if result.report:
        print(result.report)
    print("Model saved to models/")
