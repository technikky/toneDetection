"""Bootstraps an offline training set for the solfège classifier (Stage 8).

There is no internet access to a labeled corpus of sung "Do/Re/Mi/..."
syllables in this air-gapped project, so this script synthesizes one from
first principles: each syllable is modeled as a phonetic onset (plosive /
fricative / nasal / liquid / rhotic, matching the syllable's real consonant)
followed by a formant-synthesized sustained vowel at a sung pitch. Multiple
pitches and noise seeds give the classifier pitch-invariant, syllable-onset
features to learn from.

This is a bootstrap/placeholder dataset so the pipeline is trainable and
demoable fully offline out of the box. For production accuracy, replace it
by pointing this script (or train_solfege_classifier.py) at real recorded
student samples organized the same way: app/data/training/<Syllable>/*.wav
"""
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import TRAINING_DIR, SOLFEGE_SYLLABLES, SAMPLE_RATE

RNG = np.random.default_rng(42)

# (onset_type, vowel_formants (F1, F2, F3)) per solfège syllable.
SYLLABLE_PHONETICS = {
    "Do":  ("plosive_d", (500, 900, 2500)),
    "Re":  ("rhotic_r", (500, 1900, 2500)),
    "Mi":  ("nasal_m", (300, 2300, 3000)),
    "Fa":  ("fricative_f", (700, 1200, 2500)),
    "Sol": ("fricative_s", (500, 900, 2500)),
    "La":  ("liquid_l", (700, 1200, 2500)),
    "Ti":  ("plosive_t", (300, 2300, 3000)),
}

MIDI_PITCHES = list(range(48, 85, 4))   # C3..C6-ish, every ~4 semitones
VARIATIONS_PER_PITCH = 6
DURATION = 0.65


def midi_to_hz(m):
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


def formant_vowel(n, sr, f0, formants, jitter):
    """Additive-synthesis vowel: harmonics of f0 shaped by formant resonances."""
    t = np.arange(n) / sr
    n_harmonics = int(min(40, (sr / 2) / f0))
    signal = np.zeros(n)
    for h in range(1, n_harmonics + 1):
        freq = f0 * h * (1 + jitter * RNG.normal(0, 0.002))
        amp = 0.0
        for f_formant, bw in zip(formants, (120, 160, 200)):
            amp += np.exp(-0.5 * ((freq - f_formant) / bw) ** 2)
        amp *= 1.0 / h ** 0.5
        phase = RNG.uniform(0, 2 * np.pi)
        signal += amp * np.sin(2 * np.pi * freq * t + phase)
    vibrato = 1 + 0.01 * np.sin(2 * np.pi * 5.5 * t)
    signal *= vibrato
    peak = np.max(np.abs(signal)) or 1.0
    return signal / peak


def onset_segment(onset_type, sr, vowel_formants):
    if onset_type.startswith("plosive"):
        n = int(sr * 0.02)
        burst = RNG.normal(0, 1, n) * np.linspace(1, 0, n) ** 2
        gap = np.zeros(int(sr * 0.01))
        return np.concatenate([burst, gap]) * 0.6
    if onset_type.startswith("fricative"):
        n = int(sr * 0.11)
        noise = RNG.normal(0, 1, n)
        # crude spectral tilt: /s/ emphasizes high freq, /f/ stays broadband
        if onset_type.endswith("s"):
            kernel = np.array([1, -0.9])
            noise = np.convolve(noise, kernel, mode="same")
        env = np.linspace(0.3, 1.0, n) * np.linspace(1.0, 0.4, n)
        return noise * env * 0.35
    if onset_type.startswith("nasal"):
        n = int(sr * 0.09)
        t = np.arange(n) / sr
        hum = np.sin(2 * np.pi * 250 * t) + 0.5 * np.sin(2 * np.pi * 500 * t)
        env = np.linspace(0.2, 0.8, n)
        return hum * env * 0.3
    if onset_type.startswith("liquid") or onset_type.startswith("rhotic"):
        n = int(sr * 0.08)
        t = np.arange(n) / sr
        f2_start = vowel_formants[1] * (0.55 if onset_type.startswith("rhotic") else 0.8)
        f2_glide = np.linspace(f2_start, vowel_formants[1], n)
        phase = 2 * np.pi * np.cumsum(f2_glide) / sr
        glide = np.sin(phase) * np.linspace(0.3, 0.8, n)
        return glide * 0.3
    return np.zeros(int(sr * 0.03))


def synth_syllable(label, midi_pitch, sr, jitter_seed):
    onset_type, formants = SYLLABLE_PHONETICS[label]
    f0 = midi_to_hz(midi_pitch)
    onset = onset_segment(onset_type, sr, formants)
    vowel_n = int(sr * DURATION) - len(onset)
    vowel = formant_vowel(vowel_n, sr, f0, formants, jitter_seed)
    attack = min(int(sr * 0.03), vowel_n // 4)
    release = min(int(sr * 0.08), vowel_n // 4)
    env = np.ones(vowel_n)
    env[:attack] = np.linspace(0, 1, attack)
    env[-release:] = np.linspace(1, 0, release)
    vowel *= env
    audio = np.concatenate([onset, vowel])
    audio += RNG.normal(0, 0.01, audio.shape)  # room-tone augmentation
    peak = np.max(np.abs(audio)) or 1.0
    return (audio / peak * 0.9).astype(np.float32)


def main():
    if TRAINING_DIR.exists():
        shutil.rmtree(TRAINING_DIR)
    TRAINING_DIR.mkdir(parents=True)

    total = 0
    for label in SOLFEGE_SYLLABLES:
        out_dir = TRAINING_DIR / label
        out_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for midi_pitch in MIDI_PITCHES:
            for v in range(VARIATIONS_PER_PITCH):
                audio = synth_syllable(label, midi_pitch, SAMPLE_RATE, jitter_seed=v)
                sf.write(out_dir / f"{label}_{midi_pitch}_{v}.wav", audio, SAMPLE_RATE)
                count += 1
        total += count
        print(f"  {label}: {count} samples -> {out_dir}")

    print(f"Done. Generated {total} synthetic training samples in {TRAINING_DIR}")


if __name__ == "__main__":
    main()
