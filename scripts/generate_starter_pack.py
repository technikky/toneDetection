"""Stage 15: generate a progressive, Kodaly-style "starter pack" of
exercises so the app isn't an empty editor on first launch.

Each pattern is hand-curated (not randomly generated) as a sequence of
(solfege, duration_in_beats) pairs, in movable-do C major throughout --
teachers can transpose via the editor if they want a different key.
Progression: single-pitch rhythm drills (Ta / Ti-ti), then the classic
Kodaly melodic sequence Sol-Mi -> Sol-Mi-La -> Do-Re-Mi -> the anhemitonic
pentatonic (Do-Re-Mi-Sol-La, no Fa/Ti) -> the lower pentachord (adds Fa)
-> full diatonic.

Run from the project root: python scripts/generate_starter_pack.py
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SONGS_DIR = REPO_ROOT / "app" / "data" / "songs"

TEMPO_BPM = 88
KEY = "C"

# Movable-do semitone offsets from the tonic (must match app/config.py).
SOLFEGE_SEMITONES = {"Do": 0, "Re": 2, "Mi": 4, "Fa": 5, "Sol": 7, "La": 9, "Ti": 11}
TONIC_MIDI = 60  # C4


def _midi_for(solfege: str, octave_up: bool = False) -> int:
    return TONIC_MIDI + SOLFEGE_SEMITONES[solfege] + (12 if octave_up else 0)


def _abc_pitch(solfege: str, octave_up: bool) -> str:
    letter = {"Do": "C", "Re": "D", "Mi": "E", "Fa": "F", "Sol": "G", "La": "A", "Ti": "B"}[solfege]
    return letter.lower() if octave_up else letter


def _abc_duration(beats: float) -> str:
    if beats == 1:
        return ""
    if beats == int(beats):
        return str(int(beats))
    if beats == 0.5:
        return "/2"
    # Fallback for anything else (e.g. 1.5 -> "3/2")
    from fractions import Fraction
    frac = Fraction(beats).limit_denominator(8)
    return "" if frac == 1 else (f"/{frac.denominator}" if frac.numerator == 1 else f"{frac.numerator}/{frac.denominator}")


def build_song(song_id: str, title: str, difficulty: str, pattern: list) -> dict:
    """pattern: list of (solfege, beats) or (solfege, beats, octave_up)."""
    seconds_per_beat = 60.0 / TEMPO_BPM
    notes, abc_tokens = [], []
    cursor_beats = 0.0
    for step, item in enumerate(pattern, start=1):
        solfege, beats = item[0], item[1]
        octave_up = item[2] if len(item) > 2 else False
        notes.append({
            "step": step,
            "midi": _midi_for(solfege, octave_up),
            "solfege": solfege,
            "start": round(cursor_beats * seconds_per_beat, 3),
            "duration": round(beats * seconds_per_beat, 3),
        })
        abc_tokens.append(_abc_pitch(solfege, octave_up) + _abc_duration(beats))
        cursor_beats += beats
        if step % 4 == 0:
            abc_tokens.append("|")
    if abc_tokens and abc_tokens[-1] != "|":
        abc_tokens.append("|")
    abc_tokens[-1] = "|]"

    abc = f"X:1\nT:{title}\nM:4/4\nL:1/4\nQ:1/4={TEMPO_BPM}\nK:{KEY}\n{' '.join(abc_tokens)}"
    return {
        "id": song_id, "title": title, "difficulty": difficulty, "key": KEY,
        "tempo_bpm": TEMPO_BPM, "abc": abc, "notes": notes,
    }


# -- Tier A: rhythm drills (monotone on Do -- "Ta" = 1 beat, "Ti-ti" = paired eighths) --
TIER_A = [
    ("starter-rhythm-1-steady-ta", "Rhythm Drill: Steady Ta", "Beginner",
     [("Do", 1)] * 8),
    ("starter-rhythm-2-ta-titi", "Rhythm Drill: Ta and Ti-ti", "Beginner",
     [("Do", 1), ("Do", 0.5), ("Do", 0.5), ("Do", 1), ("Do", 0.5), ("Do", 0.5), ("Do", 1), ("Do", 1)]),
    ("starter-rhythm-3-titi-focus", "Rhythm Drill: Ti-ti Focus", "Beginner",
     [("Do", 0.5), ("Do", 0.5), ("Do", 0.5), ("Do", 0.5), ("Do", 1), ("Do", 0.5), ("Do", 0.5), ("Do", 1)]),
    ("starter-rhythm-4-long-short", "Rhythm Drill: Long and Short", "Beginner",
     [("Do", 2), ("Do", 1), ("Do", 0.5), ("Do", 0.5), ("Do", 2), ("Do", 2)]),
]

# -- Tier B: Sol-Mi, the universal "cuckoo" 2-note interval --
TIER_B = [
    ("starter-solmi-1-cuckoo", "Sol-Mi: Cuckoo Call", "Beginner",
     [("Sol", 1), ("Mi", 1)] * 4),
    ("starter-solmi-2-echo", "Sol-Mi: Echo Game", "Beginner",
     [("Sol", 1), ("Sol", 1), ("Mi", 1), ("Mi", 1), ("Sol", 1), ("Mi", 1), ("Sol", 2)]),
    ("starter-solmi-3-titi", "Sol-Mi: with Ti-ti", "Beginner",
     [("Sol", 0.5), ("Sol", 0.5), ("Mi", 1), ("Sol", 0.5), ("Sol", 0.5), ("Mi", 1), ("Sol", 1), ("Mi", 1)]),
    ("starter-solmi-4-question", "Sol-Mi: Question and Answer", "Beginner",
     [("Mi", 1), ("Sol", 1), ("Mi", 1), ("Mi", 1), ("Sol", 1), ("Mi", 1), ("Mi", 2)]),
]

# -- Tier C: Sol-Mi-La (adds the note above Sol) --
TIER_C = [
    ("starter-solmila-1-rise", "Sol-Mi-La: Rise and Fall", "Beginner",
     [("Mi", 1), ("Sol", 1), ("La", 1), ("Sol", 1), ("Mi", 1), ("Sol", 1), ("Mi", 2)]),
    ("starter-solmila-2-skip", "Sol-Mi-La: Skipping", "Beginner",
     [("La", 1), ("Sol", 1), ("Mi", 1), ("Sol", 1), ("La", 1), ("Mi", 2)]),
    ("starter-solmila-3-titi", "Sol-Mi-La: with Ti-ti", "Beginner",
     [("Sol", 0.5), ("La", 0.5), ("Sol", 1), ("Mi", 1), ("Sol", 0.5), ("La", 0.5), ("Sol", 1), ("Mi", 1)]),
    ("starter-solmila-4-phrase", "Sol-Mi-La: Little Phrase", "Beginner",
     [("Mi", 1), ("Mi", 1), ("Sol", 1), ("La", 1), ("Sol", 1), ("Mi", 1), ("Mi", 2)]),
]

# -- Tier D: Do-Re-Mi (stepwise, introduces the tonic and second degree) --
TIER_D = [
    ("starter-doremi-1-scale", "Do-Re-Mi: Steps Up and Down", "Beginner",
     [("Do", 1), ("Re", 1), ("Mi", 1), ("Re", 1), ("Do", 1), ("Re", 1), ("Do", 2)]),
    ("starter-doremi-2-mixed", "Do-Re-Mi: Mixed Steps", "Beginner",
     [("Mi", 1), ("Re", 1), ("Do", 1), ("Re", 1), ("Mi", 1), ("Mi", 1), ("Re", 2)]),
    ("starter-doremi-3-titi", "Do-Re-Mi: with Ti-ti", "Beginner",
     [("Do", 0.5), ("Re", 0.5), ("Mi", 1), ("Re", 0.5), ("Do", 0.5), ("Re", 1), ("Do", 2)]),
    ("starter-doremi-4-phrase", "Do-Re-Mi: Little Tune", "Beginner",
     [("Do", 1), ("Mi", 1), ("Re", 1), ("Do", 1), ("Re", 1), ("Mi", 1), ("Do", 2)]),
]

# -- Tier E: the anhemitonic (Kodaly) pentatonic: Do-Re-Mi-Sol-La, no Fa/Ti --
TIER_E = [
    ("starter-pentatonic-1-full", "Pentatonic: Full Scale", "Intermediate",
     [("Do", 1), ("Re", 1), ("Mi", 1), ("Sol", 1), ("La", 1), ("Sol", 1), ("Mi", 1), ("Do", 2)]),
    ("starter-pentatonic-2-skips", "Pentatonic: Skips and Steps", "Intermediate",
     [("Do", 1), ("Mi", 1), ("Sol", 1), ("La", 1), ("Sol", 1), ("Mi", 1), ("Re", 1), ("Do", 2)]),
    ("starter-pentatonic-3-titi", "Pentatonic: with Ti-ti", "Intermediate",
     [("Do", 0.5), ("Re", 0.5), ("Mi", 1), ("Sol", 0.5), ("La", 0.5), ("Sol", 1), ("Mi", 1), ("Do", 2)]),
    ("starter-pentatonic-4-melody", "Pentatonic: Folk Melody", "Intermediate",
     [("Sol", 1), ("Mi", 1), ("Do", 1), ("Re", 1), ("Mi", 1), ("Sol", 1), ("La", 1), ("Sol", 2)]),
]

# -- Tier F: lower pentachord Do-Re-Mi-Fa-Sol (introduces Fa) --
TIER_F = [
    ("starter-pentachord-1-scale", "Lower Pentachord: Steps", "Intermediate",
     [("Do", 1), ("Re", 1), ("Mi", 1), ("Fa", 1), ("Sol", 1), ("Fa", 1), ("Mi", 1), ("Do", 2)]),
    ("starter-pentachord-2-mixed", "Lower Pentachord: Mixed", "Intermediate",
     [("Do", 1), ("Mi", 1), ("Fa", 1), ("Sol", 1), ("Fa", 1), ("Re", 1), ("Mi", 1), ("Do", 2)]),
    ("starter-pentachord-3-titi", "Lower Pentachord: with Ti-ti", "Intermediate",
     [("Do", 0.5), ("Re", 0.5), ("Mi", 0.5), ("Fa", 0.5), ("Sol", 1), ("Fa", 1), ("Mi", 1), ("Do", 2)]),
    ("starter-pentachord-4-phrase", "Lower Pentachord: Phrase", "Intermediate",
     [("Sol", 1), ("Fa", 1), ("Mi", 1), ("Re", 1), ("Do", 1), ("Mi", 1), ("Sol", 1), ("Do", 2)]),
]

# -- Tier G: full diatonic scale Do..Ti..Do' -- "Advanced" --
TIER_G = [
    ("starter-diatonic-1-scale", "Full Scale: Do to Do", "Advanced",
     [("Do", 1), ("Re", 1), ("Mi", 1), ("Fa", 1), ("Sol", 1), ("La", 1), ("Ti", 1), ("Do", 1, True)]),
    ("starter-diatonic-2-descend", "Full Scale: Descending", "Advanced",
     [("Do", 1, True), ("Ti", 1), ("La", 1), ("Sol", 1), ("Fa", 1), ("Mi", 1), ("Re", 1), ("Do", 2)]),
    ("starter-diatonic-3-leaps", "Full Scale: Leading Tone Leaps", "Advanced",
     [("Do", 1), ("Mi", 1), ("Sol", 1), ("Ti", 1), ("Do", 1, True), ("Sol", 1), ("Ti", 1), ("Do", 2, True)]),
    ("starter-diatonic-4-phrase", "Full Scale: Closing Phrase", "Advanced",
     [("Sol", 1), ("La", 1), ("Ti", 1), ("Do", 1, True), ("Ti", 1), ("La", 1), ("Sol", 1), ("Do", 2)]),
]

ALL_TIERS = TIER_A + TIER_B + TIER_C + TIER_D + TIER_E + TIER_F + TIER_G


def main():
    SONGS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for song_id, title, difficulty, pattern in ALL_TIERS:
        song = build_song(song_id, title, difficulty, pattern)
        (SONGS_DIR / f"{song_id}.json").write_text(json.dumps(song, indent=2), encoding="utf-8")
        written += 1
    print(f"Wrote {written} starter-pack exercises to {SONGS_DIR}")


if __name__ == "__main__":
    main()
