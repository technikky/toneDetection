"""Stage 9: bi-factor matrix grading engine.

Combines the pitch-tracking pipeline (Stage 7) and the solfège classifier
(Stage 8) to score a student's recording against a target note/syllable
matrix, producing independent Pitch Accuracy and Pronunciation Accuracy
percentages plus a time-aligned per-note breakdown for the error graph.
"""
from typing import List

import numpy as np

from app.config import PITCH_TOLERANCE_SEMITONES, SOLFEGE_CONFIDENCE_FLOOR
from app.dsp import pitch as pitch_dsp
from app.dsp import solfege as solfege_dsp
from app.schemas import NoteResult, TargetNote


def _rescale_windows(notes: List[TargetNote], recording_duration: float):
    """Proportionally map the authored note timings onto the actual length
    of the student's recording, so a slightly faster/slower take still
    aligns note-by-note (simple linear time-warp; no DTW/onset detection).
    """
    if not notes:
        return []
    score_end = max(n.start + n.duration for n in notes)
    if score_end <= 0:
        return []
    scale = recording_duration / score_end
    windows = []
    for n in notes:
        start = n.start * scale
        end = (n.start + n.duration) * scale
        windows.append((start, end))
    return windows


def grade_submission(y: np.ndarray, sr: int, notes: List[TargetNote]):
    duration = len(y) / sr if sr else 0.0
    times, midi_contour, voiced_flag = pitch_dsp.extract_pitch_contour(y, sr)
    windows = _rescale_windows(notes, duration)

    results: List[NoteResult] = []
    pitch_hits = 0
    solfege_hits = 0
    solfege_ready = solfege_dsp.is_ready()

    for note, (w_start, w_end) in zip(notes, windows):
        detected_midi = pitch_dsp.note_window_pitch(times, midi_contour, voiced_flag, w_start, w_end)
        pitch_correct = (
            detected_midi is not None
            and abs(detected_midi - note.midi) <= PITCH_TOLERANCE_SEMITONES
        )
        detected_note_name = (
            pitch_dsp.midi_to_note_name(detected_midi) if detected_midi is not None else None
        )

        detected_solfege, confidence = None, 0.0
        solfege_correct = False
        if solfege_ready:
            start_sample = int(max(w_start, 0) * sr)
            end_sample = int(max(w_end, w_start) * sr)
            window_audio = y[start_sample:end_sample]
            detected_solfege, confidence = solfege_dsp.classify_window(window_audio, sr)
            solfege_correct = (
                detected_solfege == note.solfege and confidence >= SOLFEGE_CONFIDENCE_FLOOR
            )

        if pitch_correct:
            pitch_hits += 1
        if solfege_correct:
            solfege_hits += 1

        results.append(NoteResult(
            step=note.step,
            start=note.start,
            duration=note.duration,
            target_midi=note.midi,
            target_solfege=note.solfege,
            detected_midi=detected_midi,
            detected_note_name=detected_note_name,
            pitch_correct=pitch_correct,
            detected_solfege=detected_solfege,
            solfege_confidence=round(confidence, 3),
            solfege_correct=solfege_correct,
        ))

    total = len(notes) or 1
    pitch_accuracy = round(100.0 * pitch_hits / total, 1)
    pronunciation_accuracy = round(100.0 * solfege_hits / total, 1)
    overall_score = round((pitch_accuracy + pronunciation_accuracy) / 2, 1)

    # Sparse contour for the front-end error graph: [time, midi] pairs, voiced only.
    contour = [
        [round(float(t), 3), round(float(m), 2)]
        for t, m, v in zip(times, midi_contour, voiced_flag)
        if v
    ][::4]  # thin out for payload size

    return {
        "pitch_accuracy": pitch_accuracy,
        "pronunciation_accuracy": pronunciation_accuracy,
        "overall_score": overall_score,
        "notes": results,
        "pitch_contour": contour,
    }
