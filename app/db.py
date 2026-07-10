"""Stage 12: local SQLite record-keeping for students and graded takes.

Kept deliberately simple (stdlib sqlite3, one connection per call) since
this is a single-teacher, single-machine, low-concurrency offline tool.
"""
import json
import sqlite3
from datetime import datetime
from typing import Optional

from app.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id),
    song_id TEXT NOT NULL,
    song_title TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    pitch_accuracy REAL NOT NULL,
    pronunciation_accuracy REAL NOT NULL,
    overall_score REAL NOT NULL,
    notes_json TEXT NOT NULL,
    take_filename TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_submissions_submitted_at ON submissions(submitted_at);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def count_teachers() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM teachers").fetchone()["n"]


def create_teacher(username: str, password_hash: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO teachers (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username.strip(), password_hash, datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def get_teacher_by_username(username: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM teachers WHERE username = ? COLLATE NOCASE",
            (username.strip(),),
        ).fetchone()
        return dict(row) if row else None


def get_or_create_student(name: str) -> int:
    name = name.strip()
    with _connect() as conn:
        row = conn.execute("SELECT id FROM students WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO students (name, created_at) VALUES (?, ?)",
            (name, datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def record_submission(
    student_name: str,
    song_id: str,
    song_title: str,
    report: dict,
    take_filename: str,
) -> int:
    student_id = get_or_create_student(student_name)
    notes = [n.model_dump() if hasattr(n, "model_dump") else n for n in report["notes"]]
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO submissions
               (student_id, song_id, song_title, submitted_at, pitch_accuracy,
                pronunciation_accuracy, overall_score, notes_json, take_filename)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                student_id,
                song_id,
                song_title,
                datetime.now().isoformat(timespec="seconds"),
                report["pitch_accuracy"],
                report["pronunciation_accuracy"],
                report["overall_score"],
                json.dumps(notes),
                take_filename,
            ),
        )
        return cur.lastrowid


def list_submissions(date: Optional[str] = None, student_name: Optional[str] = None) -> list:
    """List submissions, newest first. `date` filters to a 'YYYY-MM-DD' local day."""
    query = """
        SELECT s.id, st.name AS student_name, s.song_id, s.song_title, s.submitted_at,
               s.pitch_accuracy, s.pronunciation_accuracy, s.overall_score
        FROM submissions s JOIN students st ON st.id = s.student_id
        WHERE 1=1
    """
    params: list = []
    if date:
        query += " AND substr(s.submitted_at, 1, 10) = ?"
        params.append(date)
    if student_name:
        query += " AND st.name LIKE ? ESCAPE '\\' COLLATE NOCASE"
        escaped = student_name.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")
    query += " ORDER BY s.submitted_at DESC"

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def list_students() -> list:
    with _connect() as conn:
        rows = conn.execute("SELECT name FROM students ORDER BY name COLLATE NOCASE").fetchall()
        return [r["name"] for r in rows]
