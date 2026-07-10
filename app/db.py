"""Stage 12/15: local SQLite record-keeping for teachers, the student
roster, and graded takes.

Kept deliberately simple (stdlib sqlite3, one connection per call) since
this is a single-teacher, single-machine, low-concurrency offline tool.
"""
import json
import secrets
import sqlite3
from datetime import datetime
from typing import Optional

from app import roster_crypto
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
    access_code TEXT NOT NULL UNIQUE,
    name_encrypted BLOB NOT NULL,
    consent_on_file INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
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

# Excludes visually-ambiguous characters (0/O, 1/I/L) since students read
# these off a card or the board.
_ACCESS_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_ACCESS_CODE_LENGTH = 6


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


# -- teachers --------------------------------------------------------------

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


# -- roster ------------------------------------------------------------

def _generate_access_code(conn: sqlite3.Connection) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(_ACCESS_CODE_ALPHABET) for _ in range(_ACCESS_CODE_LENGTH))
        exists = conn.execute("SELECT 1 FROM students WHERE access_code = ?", (code,)).fetchone()
        if not exists:
            return code
    raise RuntimeError("Could not generate a unique access code after 20 attempts.")


def add_student(name: str, consent_on_file: bool) -> dict:
    name = name.strip()
    with _connect() as conn:
        code = _generate_access_code(conn)
        created_at = datetime.now().isoformat(timespec="seconds")
        cur = conn.execute(
            """INSERT INTO students (access_code, name_encrypted, consent_on_file, active, created_at)
               VALUES (?, ?, ?, 1, ?)""",
            (code, roster_crypto.encrypt_name(name), int(consent_on_file), created_at),
        )
        return {"id": cur.lastrowid, "access_code": code, "name": name,
                "consent_on_file": consent_on_file, "active": True, "created_at": created_at}


def list_roster() -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, access_code, name_encrypted, consent_on_file, active, created_at "
            "FROM students ORDER BY created_at"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "access_code": r["access_code"],
            "name": roster_crypto.decrypt_name(r["name_encrypted"]),
            "consent_on_file": bool(r["consent_on_file"]),
            "active": bool(r["active"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def get_student_by_code(access_code: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, access_code, name_encrypted, active FROM students WHERE access_code = ?",
            (access_code.strip().upper(),),
        ).fetchone()
    if not row or not row["active"]:
        return None
    return {"id": row["id"], "access_code": row["access_code"], "name": roster_crypto.decrypt_name(row["name_encrypted"])}


def set_student_active(student_id: int, active: bool) -> bool:
    with _connect() as conn:
        cur = conn.execute("UPDATE students SET active = ? WHERE id = ?", (int(active), student_id))
        return cur.rowcount > 0


# -- submissions -------------------------------------------------------

def record_submission(
    student_id: int,
    song_id: str,
    song_title: str,
    report: dict,
    take_filename: str,
) -> int:
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
    """List submissions, newest first. `date` filters to a 'YYYY-MM-DD' local
    day. Names are encrypted at rest, so the optional name filter is applied
    in Python after decrypting -- fine at classroom scale."""
    query = """
        SELECT s.id, st.name_encrypted, s.song_id, s.song_title, s.submitted_at,
               s.pitch_accuracy, s.pronunciation_accuracy, s.overall_score
        FROM submissions s JOIN students st ON st.id = s.student_id
        WHERE 1=1
    """
    params: list = []
    if date:
        query += " AND substr(s.submitted_at, 1, 10) = ?"
        params.append(date)
    query += " ORDER BY s.submitted_at DESC"

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    results = []
    needle = student_name.strip().lower() if student_name else None
    for r in rows:
        name = roster_crypto.decrypt_name(r["name_encrypted"])
        if needle and needle not in name.lower():
            continue
        row = dict(r)
        row.pop("name_encrypted")
        row["student_name"] = name
        results.append(row)
    return results


def list_submissions_for_code(access_code: str) -> list:
    """A student's own past attempts, looked up by their own access code."""
    student = get_student_by_code(access_code)
    if not student:
        return []
    with _connect() as conn:
        rows = conn.execute(
            """SELECT id, song_id, song_title, submitted_at, pitch_accuracy,
                      pronunciation_accuracy, overall_score
               FROM submissions WHERE student_id = ? ORDER BY submitted_at DESC""",
            (student["id"],),
        ).fetchall()
    return [dict(r) for r in rows]
