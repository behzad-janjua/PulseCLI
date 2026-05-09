import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from pulse.training import WINDOW_SAMPLES, train_classifier


class TestTrainClassifier(unittest.TestCase):
    def test_trains_from_exact_window_sample(self):
        with TemporaryDirectory() as data, TemporaryDirectory() as models:
            data_dir = Path(data)
            model_dir = Path(models)
            np.save(
                data_dir / "pinch_000.npy",
                np.ones((WINDOW_SAMPLES, 8), dtype=np.float32),
            )

            result = train_classifier(data_dir, model_dir, verbose=False)

            self.assertEqual(result.classes, ["pinch"])
            self.assertEqual(result.samples, 1)
            self.assertTrue((model_dir / "gesture_classifier.pkl").exists())
            self.assertTrue((model_dir / "label_encoder.pkl").exists())


if __name__ == "__main__":
    unittest.main()
