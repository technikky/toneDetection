"""Pydantic response/request models shared across routes."""
from typing import List, Optional
from pydantic import BaseModel


class TargetNote(BaseModel):
    step: int
    midi: int
    solfege: str
    start: float
    duration: float


class SongSummary(BaseModel):
    id: str
    title: str
    difficulty: str
    key: str
    tempo_bpm: int


class SongDetail(SongSummary):
    abc: str
    notes: List[TargetNote]


class SongPayload(BaseModel):
    """Body for creating/updating an exercise (Stage 12 sheet-music editor)."""
    title: str
    difficulty: str
    key: str
    tempo_bpm: int
    abc: str
    notes: List[TargetNote]


class NoteResult(BaseModel):
    step: int
    start: float
    duration: float
    target_midi: int
    target_solfege: str
    detected_midi: Optional[float]
    detected_note_name: Optional[str]
    pitch_correct: bool
    detected_solfege: Optional[str]
    solfege_confidence: float
    solfege_correct: bool


class AssessmentReport(BaseModel):
    song_id: str
    pitch_accuracy: float
    pronunciation_accuracy: float
    overall_score: float
    notes: List[NoteResult]
    pitch_contour: List[List[float]]  # [[time, midi], ...] sparse, for the error graph


class SubmissionRecord(BaseModel):
    """One row of the Stage 12 teacher submissions history."""
    id: int
    student_name: str
    song_id: str
    song_title: str
    submitted_at: str
    pitch_accuracy: float
    pronunciation_accuracy: float
    overall_score: float
