"""Central paths and constants for the offline sight-singing app."""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FROZEN = getattr(sys, "frozen", False)

# Stage 11: when frozen by PyInstaller, bundled read-only assets (templates,
# static, songs, the trained classifier) live under the one-file extraction
# dir (sys._MEIPASS) instead of next to this file. Writable data must live
# next to the .exe instead, since _MEIPASS is a temp dir wiped on exit.
APP_ROOT = Path(sys._MEIPASS).resolve() / "app" if FROZEN else BASE_DIR
WRITABLE_DIR = (Path(sys.executable).resolve().parent / "data") if FROZEN else (BASE_DIR / "data")

STATIC_DIR = APP_ROOT / "static"
TEMPLATES_DIR = APP_ROOT / "templates"
SONGS_DIR = APP_ROOT / "data" / "songs"
MODELS_DIR = APP_ROOT / "models"
SOLFEGE_MODEL_PATH = MODELS_DIR / "solfege_classifier.joblib"

UPLOADS_DIR = WRITABLE_DIR / "uploads"
TRAINING_DIR = BASE_DIR / "data" / "training"

for _d in (UPLOADS_DIR, MODELS_DIR, SONGS_DIR):
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
