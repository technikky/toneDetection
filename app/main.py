"""Core FastAPI server (Stage 2): page routing, exercise catalog, and the
audio submission endpoint that drives the Stage 9 grading engine.
"""
import io
import json
import logging
import re
import time
import uuid
from datetime import date as date_cls
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app import db
from app.config import SONGS_DIR, STATIC_DIR, TEMPLATES_DIR, UPLOADS_DIR, SAMPLE_RATE
from app.dsp import solfege as solfege_dsp
from app.dsp.grading import grade_submission
from app.live import manager as live_manager
from app.musicxml_import import MusicXmlImportError, parse_musicxml
from app.schemas import AssessmentReport, SongDetail, SongPayload, SongSummary, SubmissionRecord

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sight_singing")

app = FastAPI(title="Offline Sight-Singing & Solfège Assessment Tool")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

db.init_db()


def _load_song(song_id: str) -> dict:
    path = SONGS_DIR / f"{song_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Unknown exercise '{song_id}'")
    return json.loads(path.read_text(encoding="utf-8"))


def _list_songs() -> list:
    songs = []
    for path in sorted(SONGS_DIR.glob("*.json")):
        songs.append(json.loads(path.read_text(encoding="utf-8")))
    return songs


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")
    return slug or "exercise"


def _unique_song_id(title: str) -> str:
    base = _slugify(title)
    song_id = base
    n = 2
    while (SONGS_DIR / f"{song_id}.json").exists():
        song_id = f"{base}-{n}"
        n += 1
    return song_id


def _save_song(song_id: str, payload: SongPayload) -> dict:
    if not payload.notes:
        raise HTTPException(status_code=400, detail="An exercise needs at least one note.")
    song = {
        "id": song_id,
        "title": payload.title.strip(),
        "difficulty": payload.difficulty.strip(),
        "key": payload.key.strip(),
        "tempo_bpm": payload.tempo_bpm,
        "abc": payload.abc,
        "notes": [n.model_dump() for n in payload.notes],
    }
    (SONGS_DIR / f"{song_id}.json").write_text(json.dumps(song, indent=2), encoding="utf-8")
    return song


@app.get("/", response_class=HTMLResponse)
async def role_picker(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/teacher", response_class=HTMLResponse)
async def teacher_dashboard(request: Request):
    return templates.TemplateResponse(request, "teacher.html", {"songs": _list_songs()})


@app.get("/teacher/submissions", response_class=HTMLResponse)
async def teacher_submissions_page(request: Request, date: str | None = None):
    selected_date = date or date_cls.today().isoformat()
    return templates.TemplateResponse(
        request,
        "teacher_submissions.html",
        {"selected_date": selected_date},
    )


@app.get("/teacher/editor", response_class=HTMLResponse)
async def teacher_editor_page(request: Request, song: str | None = None):
    existing_song = _load_song(song) if song else None
    return templates.TemplateResponse(
        request,
        "editor.html",
        {"songs": _list_songs(), "existing_song": existing_song},
    )


@app.get("/teacher/monitor", response_class=HTMLResponse)
async def teacher_monitor_page(request: Request, song: str | None = None):
    songs = _list_songs()
    selected_song_id = song if (song and any(s["id"] == song for s in songs)) else (songs[0]["id"] if songs else None)
    return templates.TemplateResponse(
        request,
        "monitor.html",
        {"songs": songs, "selected_song_id": selected_song_id},
    )


@app.get("/student", response_class=HTMLResponse)
async def student_dashboard(request: Request, song: str | None = None):
    songs = _list_songs()
    if not songs:
        raise HTTPException(status_code=500, detail="No exercises configured on the server.")
    selected = song or songs[0]["id"]
    return templates.TemplateResponse(
        request,
        "student.html",
        {"songs": songs, "selected_song_id": selected,
         "solfege_ready": solfege_dsp.is_ready()},
    )


@app.get("/api/songs", response_model=list[SongSummary])
async def api_list_songs():
    return [
        SongSummary(id=s["id"], title=s["title"], difficulty=s["difficulty"],
                    key=s["key"], tempo_bpm=s["tempo_bpm"])
        for s in _list_songs()
    ]


@app.get("/api/songs/{song_id}", response_model=SongDetail)
async def api_get_song(song_id: str):
    return SongDetail(**_load_song(song_id))


@app.post("/api/songs", response_model=SongDetail, status_code=201)
async def api_create_song(payload: SongPayload):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title is required.")
    song_id = _unique_song_id(payload.title)
    song = _save_song(song_id, payload)
    return SongDetail(**song)


@app.put("/api/songs/{song_id}", response_model=SongDetail)
async def api_update_song(song_id: str, payload: SongPayload):
    _load_song(song_id)  # 404s if it doesn't already exist
    song = _save_song(song_id, payload)
    return SongDetail(**song)


@app.post("/api/songs/import-musicxml", response_model=SongPayload)
async def api_import_musicxml(file: UploadFile = File(...)):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file upload.")
    fallback_title = Path(file.filename).stem if file.filename else "Imported Exercise"
    try:
        parsed = parse_musicxml(raw, fallback_title=fallback_title)
    except MusicXmlImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SongPayload(**parsed)


@app.get("/api/status")
async def api_status():
    return {"solfege_classifier_ready": solfege_dsp.is_ready(), "sample_rate": SAMPLE_RATE}


@app.get("/api/submissions", response_model=list[SubmissionRecord])
async def api_list_submissions(date: str | None = None, student: str | None = None):
    return [SubmissionRecord(**row) for row in db.list_submissions(date=date, student_name=student)]


@app.get("/api/students", response_model=list[str])
async def api_list_students():
    return db.list_students()


@app.post("/api/submit", response_model=AssessmentReport)
async def submit_recording(
    song_id: str = Form(...),
    student_name: str = Form(...),
    file: UploadFile = File(...),
):
    student_name = student_name.strip()
    if not student_name:
        raise HTTPException(status_code=400, detail="student_name is required.")

    song = _load_song(song_id)
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty audio upload.")

    try:
        audio, sr = sf.read(io.BytesIO(raw_bytes), dtype="float32", always_2d=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not decode audio: {exc}") from exc

    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # Persist the take for teacher review / future retraining data.
    take_id = f"{song_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}.wav"
    sf.write(UPLOADS_DIR / take_id, audio, sr)

    from app.schemas import TargetNote
    target_notes = [TargetNote(**n) for n in song["notes"]]

    report = grade_submission(np.asarray(audio, dtype=np.float32), sr, target_notes)
    db.record_submission(
        student_name=student_name,
        song_id=song_id,
        song_title=song["title"],
        report=report,
        take_filename=take_id,
    )
    await live_manager.mark_submitted_by_name(student_name)
    return AssessmentReport(song_id=song_id, **report)


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    """Stage 14: one shared socket for both roles. Students stream live
    pitch/status; teachers receive roster + pitch updates and can push a
    "send to class" assignment that every connected student picks up.
    """
    await websocket.accept()
    role = None
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "join":
                role = data.get("role")
                if role == "student":
                    name = (data.get("student_name") or "Unknown").strip()[:60] or "Unknown"
                    await live_manager.student_join(websocket, name)
                elif role == "teacher":
                    await live_manager.teacher_join(websocket)
            elif msg_type == "status" and role == "student":
                await live_manager.student_status(websocket, str(data.get("status", "idle")))
            elif msg_type == "pitch" and role == "student":
                await live_manager.student_pitch(websocket, data.get("hz"), data.get("midi"), data.get("level"))
            elif msg_type == "assign" and role == "teacher":
                await live_manager.teacher_assign(data.get("song_id"), data.get("difficulty"))
    except WebSocketDisconnect:
        pass
    finally:
        if role == "student":
            await live_manager.student_leave(websocket)
        elif role == "teacher":
            await live_manager.teacher_leave(websocket)


def run():
    """Entrypoint used by the PyInstaller-built executable (Stage 11)."""
    import uvicorn
    import webbrowser
    import threading

    def _open_browser():
        time.sleep(1.2)
        webbrowser.open("http://127.0.0.1:8000/")

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    run()
