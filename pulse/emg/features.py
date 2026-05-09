import numpy as np


def extract_features(window: np.ndarray) -> np.ndarray:
    """
    Extract time-domain features from an EMG window.

    window: shape (n_samples, 8) — one row per sample, one column per sensor channel
    returns: 1D feature vector of length 24 (3 features × 8 channels)

    Features per channel:
      MAV — mean absolute value (signal energy)
      RMS — root mean square (signal power)
      WL  — waveform length (signal complexity / rate of change)
    """
    features = []
    for ch in range(8):
        s = window[:, ch].astype(np.float64)
        features.append(np.mean(np.abs(s)))           # MAV
        features.append(np.sqrt(np.mean(s ** 2)))     # RMS
        features.append(np.sum(np.abs(np.diff(s))))   # WL
    return np.array(features, dtype=np.float32)
