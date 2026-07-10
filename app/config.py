"""Central paths and constants for the offline sight-singing app."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
SONGS_DIR = BASE_DIR / "data" / "songs"
UPLOADS_DIR = BASE_DIR / "data" / "uploads"
TRAINING_DIR = BASE_DIR / "data" / "training"
MODELS_DIR = BASE_DIR / "models"
SOLFEGE_MODEL_PATH = MODELS_DIR / "solfege_classifier.joblib"

for _d in (UPLOADS_DIR, TRAINING_DIR, MODELS_DIR, SONGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# The seven movable-do solfège syllables this system recognizes.
SOLFEGE_SYLLABLES = ["Do", "Re", "Mi", "Fa", "Sol", "La", "Ti"]

# Diatonic major-scale semitone offsets from the tonic, in solfège order.
SOLFEGE_SEMITONE_OFFSETS = {
    "Do": 0, "Re": 2, "Mi": 4, "Fa": 5, "Sol": 7, "La": 9, "Ti": 11,
}

SAMPLE_RATE = 22050

# Pitch grading tolerance, in semitones, for a note to count as "correct".
PITCH_TOLERANCE_SEMITONES = 0.6

# Minimum classifier confidence to accept a syllable prediction outright.
SOLFEGE_CONFIDENCE_FLOOR = 0.15
