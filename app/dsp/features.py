"""Shared MFCC feature extraction used by both training and inference.

Kept in one place so the offline-trained classifier and the live grading
pipeline can never drift out of sync on feature definition.
"""
import numpy as np
import librosa

N_MFCC = 13


def extract_features(y: np.ndarray, sr: int) -> np.ndarray:
    """Fixed-length feature vector: MFCC + delta + delta2 (mean & std) plus
    spectral centroid and zero-crossing rate (mean & std).
    """
    y = np.asarray(y, dtype=float)
    if y.size < 512:
        y = np.pad(y, (0, 512 - y.size))

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    delta = librosa.feature.delta(mfcc)
    delta2 = librosa.feature.delta(mfcc, order=2)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    zcr = librosa.feature.zero_crossing_rate(y)

    parts = []
    for feat in (mfcc, delta, delta2):
        parts.append(feat.mean(axis=1))
        parts.append(feat.std(axis=1))
    parts.append(centroid.mean(axis=1) / sr)   # normalize to [0,1]-ish scale
    parts.append(centroid.std(axis=1) / sr)
    parts.append(zcr.mean(axis=1))
    parts.append(zcr.std(axis=1))

    return np.concatenate(parts).astype(np.float32)
