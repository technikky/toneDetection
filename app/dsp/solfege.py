"""Stage 8: offline solfège pronunciation classifier.

Loads a lightweight scikit-learn SVM (MFCC-based) trained entirely offline
(see scripts/train_solfege_classifier.py) and classifies short vocal windows
into one of the seven movable-do syllables.
"""
import logging
from pathlib import Path
from typing import Optional, Tuple

import joblib
import numpy as np

from app.config import SOLFEGE_MODEL_PATH
from app.dsp.features import extract_features

log = logging.getLogger(__name__)

_model = None
_label_encoder = None


def _load():
    global _model, _label_encoder
    if _model is not None:
        return
    if not Path(SOLFEGE_MODEL_PATH).exists():
        raise FileNotFoundError(
            f"Solfège classifier not found at {SOLFEGE_MODEL_PATH}. "
            "Run scripts/generate_solfege_training_data.py then "
            "scripts/train_solfege_classifier.py first."
        )
    bundle = joblib.load(SOLFEGE_MODEL_PATH)
    _model = bundle["pipeline"]
    _label_encoder = bundle["label_encoder"]
    log.info("Loaded solfège classifier from %s", SOLFEGE_MODEL_PATH)


def is_ready() -> bool:
    return Path(SOLFEGE_MODEL_PATH).exists()


def classify_window(y: np.ndarray, sr: int) -> Tuple[Optional[str], float]:
    """Return (predicted_syllable, confidence) for one audio window."""
    _load()
    if y.size == 0:
        return None, 0.0
    feats = extract_features(y, sr).reshape(1, -1)
    proba = _model.predict_proba(feats)[0]
    idx = int(np.argmax(proba))
    label = _label_encoder.inverse_transform([idx])[0]
    confidence = float(proba[idx])
    return label, confidence
