from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import numpy as np

from pulse.training import DATA_DIR, MODEL_DIR, WINDOW_SAMPLES, TrainingResult, train_classifier

LABEL_PATTERN = re.compile(r"[^a-z0-9_]+")


def sanitize_label(label: str) -> str:
    normalized = label.strip().lower().replace("-", "_").replace(" ", "_")
    normalized = LABEL_PATTERN.sub("_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        raise ValueError("Gesture label cannot be empty")
    return normalized


class LearningService:
    def __init__(
        self,
        data_dir: Path = DATA_DIR,
        model_dir: Path = MODEL_DIR,
        trainer: Callable[..., TrainingResult] = train_classifier,
    ) -> None:
        self._data_dir = data_dir
        self._model_dir = model_dir
        self._trainer = trainer
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._model_dir.mkdir(parents=True, exist_ok=True)

    def save_sample(self, label: str, samples: np.ndarray) -> Path:
        safe_label = sanitize_label(label)
        clean_samples = self._validate_samples(samples)
        path = self._next_path(safe_label)
        np.save(path, clean_samples)
        return path

    def save_trials(
        self,
        label: str,
        samples: np.ndarray,
        *,
        trials: int = 3,
    ) -> list[Path]:
        clean_samples = self._validate_samples(samples)
        if len(clean_samples) < WINDOW_SAMPLES:
            raise ValueError(
                f"Need at least {WINDOW_SAMPLES} EMG samples to teach a gesture"
            )

        if trials <= 1 or len(clean_samples) < WINDOW_SAMPLES * 2:
            return [self.save_sample(label, clean_samples)]

        max_start = len(clean_samples) - WINDOW_SAMPLES
        starts = np.linspace(0, max_start, num=trials, dtype=int)
        paths = []
        for start in starts:
            window = clean_samples[start : start + WINDOW_SAMPLES]
            paths.append(self.save_sample(label, window))
        return paths

    def retrain(self) -> TrainingResult:
        return self._trainer(self._data_dir, self._model_dir, verbose=False)

    def _next_path(self, label: str) -> Path:
        idx = len(list(self._data_dir.glob(f"{label}_*.npy")))
        return self._data_dir / f"{label}_{idx:03d}.npy"

    @staticmethod
    def _validate_samples(samples: np.ndarray) -> np.ndarray:
        arr = np.asarray(samples, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[1] != 8:
            raise ValueError("EMG samples must have shape (n_samples, 8)")
        if len(arr) == 0:
            raise ValueError("EMG sample buffer is empty")
        return arr
