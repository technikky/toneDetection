"""Core FastAPI server (Stage 2): page routing, exercise catalog, and the
audio submission endpoint that drives the Stage 9 grading engine.
"""
import io
import json
import logging
import time
import uuid

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app import db
from app.config import SONGS_DIR, STATIC_DIR, TEMPLATES_DIR, UPLOADS_DIR, SAMPLE_RATE
from app.dsp import solfege as solfege_dsp
from app.dsp.grading import grade_submission
from app.schemas import AssessmentReport, SongDetail, SongSummary

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


@app.get("/", response_class=HTMLResponse)
async def role_picker(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/teacher", response_class=HTMLResponse)
async def teacher_dashboard(request: Request):
    return templates.TemplateResponse(request, "teacher.html", {"songs": _list_songs()})


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


@app.get("/api/status")
async def api_status():
    return {"solfege_classifier_ready": solfege_dsp.is_ready(), "sample_rate": SAMPLE_RATE}


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
    return AssessmentReport(song_id=song_id, **report)


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
