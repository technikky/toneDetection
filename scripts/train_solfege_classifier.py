"""Stage 8: trains the offline MFCC + SVM solfège classifier.

Reads app/data/training/<Syllable>/*.wav (see
generate_solfege_training_data.py, or drop in real recordings using the
same folder layout), extracts MFCC-based features, and fits a scikit-learn
SVM. The resulting pipeline + label encoder are persisted to
app/models/solfege_classifier.joblib for the FastAPI backend to load.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import soundfile as sf
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import SVC

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import TRAINING_DIR, MODELS_DIR, SOLFEGE_MODEL_PATH
from app.dsp.features import extract_features


def load_dataset():
    X, y = [], []
    for label_dir in sorted(TRAINING_DIR.iterdir()):
        if not label_dir.is_dir():
            continue
        label = label_dir.name
        for wav_path in sorted(label_dir.glob("*.wav")):
            audio, sr = sf.read(wav_path)
            X.append(extract_features(audio, sr))
            y.append(label)
    return np.array(X), np.array(y)


def main():
    if not TRAINING_DIR.exists() or not any(TRAINING_DIR.iterdir()):
        print("No training data found. Run generate_solfege_training_data.py first.")
        sys.exit(1)

    print("Loading training data and extracting MFCC features...")
    X, y = load_dataset()
    print(f"Loaded {len(X)} samples across {len(set(y))} classes.")

    encoder = LabelEncoder()
    y_enc = encoder.fit_transform(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("svm", CalibratedClassifierCV(SVC(kernel="rbf", C=10, gamma="scale"), ensemble=False)),
    ])

    print("Training SVM classifier...")
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\nHeld-out accuracy: {acc:.2%}\n")
    print(classification_report(y_test, y_pred, target_names=encoder.classes_))

    # Refit on all data for the shipped model.
    pipeline.fit(X, y_enc)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "label_encoder": encoder}, SOLFEGE_MODEL_PATH)
    print(f"Saved classifier to {SOLFEGE_MODEL_PATH}")


if __name__ == "__main__":
    main()
