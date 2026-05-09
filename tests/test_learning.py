import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import numpy as np

from pulse.learning import LearningService, sanitize_label
from pulse.training import TrainingResult, WINDOW_SAMPLES


class TestSanitizeLabel(unittest.TestCase):
    def test_sanitizes_spoken_label(self):
        self.assertEqual(sanitize_label(" Panic Build! "), "panic_build")

    def test_empty_label_raises(self):
        with self.assertRaises(ValueError):
            sanitize_label(" !!! ")


class TestLearningService(unittest.TestCase):
    def test_save_sample_creates_expected_file(self):
        with TemporaryDirectory() as data, TemporaryDirectory() as models:
            service = LearningService(Path(data), Path(models))
            samples = np.ones((WINDOW_SAMPLES, 8), dtype=np.float32)

            path = service.save_sample("panic build", samples)

            self.assertEqual(path.name, "panic_build_000.npy")
            saved = np.load(path)
            self.assertEqual(saved.shape, (WINDOW_SAMPLES, 8))

    def test_save_sample_increments_index(self):
        with TemporaryDirectory() as data, TemporaryDirectory() as models:
            service = LearningService(Path(data), Path(models))
            samples = np.ones((WINDOW_SAMPLES, 8), dtype=np.float32)

            first = service.save_sample("pinch", samples)
            second = service.save_sample("pinch", samples)

            self.assertEqual(first.name, "pinch_000.npy")
            self.assertEqual(second.name, "pinch_001.npy")

    def test_save_trials_splits_recent_buffer(self):
        with TemporaryDirectory() as data, TemporaryDirectory() as models:
            service = LearningService(Path(data), Path(models))
            samples = np.ones((WINDOW_SAMPLES * 3, 8), dtype=np.float32)

            paths = service.save_trials("snap", samples, trials=3)

            self.assertEqual(len(paths), 3)
            self.assertEqual([p.name for p in paths], [
                "snap_000.npy",
                "snap_001.npy",
                "snap_002.npy",
            ])

    def test_retrain_invokes_local_trainer(self):
        result = TrainingResult(classes=["rest"], samples=10, files=1)
        trainer = Mock(return_value=result)
        with TemporaryDirectory() as data, TemporaryDirectory() as models:
            data_dir = Path(data)
            model_dir = Path(models)
            service = LearningService(data_dir, model_dir, trainer=trainer)

            self.assertIs(service.retrain(), result)
            trainer.assert_called_once_with(data_dir, model_dir, verbose=False)


if __name__ == "__main__":
    unittest.main()
