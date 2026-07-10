"""Stage 7: studio-grade fundamental frequency extraction and MIDI quantization.

Uses librosa.pyin (probabilistic YIN) for f0 tracking, then quantizes each
frame to the 12-tone equal temperament scale via the standard MIDI formula:

    d = 69 + 12 * log2(f / 440)
"""
import numpy as np
import librosa

FMIN = librosa.note_to_hz("C2")   # ~65.4 Hz
FMAX = librosa.note_to_hz("C7")   # ~2093 Hz


def hz_to_midi(f_hz: np.ndarray) -> np.ndarray:
    """12-TET quantization formula: d = 69 + 12*log2(f/440)."""
    f_hz = np.asarray(f_hz, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        midi = 69.0 + 12.0 * np.log2(f_hz / 440.0)
    return midi


def extract_pitch_contour(y: np.ndarray, sr: int):
    """Run librosa.pyin over the recording and return (times, midi, voiced_flag)."""
    if y.size == 0:
        return np.array([]), np.array([]), np.array([], dtype=bool)

    f0, voiced_flag, voiced_prob = librosa.pyin(
        y, fmin=FMIN, fmax=FMAX, sr=sr, frame_length=2048, hop_length=512
    )
    times = librosa.times_like(f0, sr=sr, hop_length=512)
    midi = hz_to_midi(f0)
    voiced_flag = np.asarray(voiced_flag, dtype=bool) & ~np.isnan(midi)
    return times, midi, voiced_flag


def note_window_pitch(times, midi, voiced_flag, start: float, end: float):
    """Median quantized MIDI pitch (rounded to nearest semitone) within [start, end)."""
    mask = (times >= start) & (times < end) & voiced_flag
    if not np.any(mask):
        return None
    window_midi = midi[mask]
    median_midi = float(np.median(window_midi))
    return median_midi


def midi_to_note_name(midi_value: float) -> str:
    return librosa.midi_to_note(int(round(midi_value)), unicode=False)
