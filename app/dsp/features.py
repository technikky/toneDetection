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

    # librosa.feature.delta needs at least `width` frames (default 9). A short
    # note window can yield fewer, so clamp width to the frames available --
    # it must be odd and >= 3. With too few frames for even a width-3 delta,
    # fall back to zeros (a flat contour is a fine stand-in here).
    n_frames = mfcc.shape[1]
    if n_frames >= 3:
        width = min(9, n_frames if n_frames % 2 == 1 else n_frames - 1)
        delta = librosa.feature.delta(mfcc, width=width)
        delta2 = librosa.feature.delta(mfcc, order=2, width=width)
    else:
        delta = np.zeros_like(mfcc)
        delta2 = np.zeros_like(mfcc)
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
