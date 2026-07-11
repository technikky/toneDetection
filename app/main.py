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
from typing import Optional

import numpy as np
import soundfile as sf
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app import auth, db, licensing
from app.config import SONGS_DIR, STATIC_DIR, TEMPLATES_DIR, UPLOADS_DIR, SAMPLE_RATE
from app.dsp import solfege as solfege_dsp
from app.dsp.grading import grade_submission
from app.live import manager as live_manager
from app.logging_config import configure_logging
from app.musicxml_import import MusicXmlImportError, parse_musicxml
from app.schemas import (
    AssessmentReport, CodeCheckResult, MySubmissionRecord, RosterAddRequest, RosterEntry,
    RosterUpdateRequest, SongDetail, SongPayload, SongSummary, SubmissionRecord,
)

configure_logging()
log = logging.getLogger("sight_singing")

app = FastAPI(title="Offline Sight-Singing & Solfège Assessment Tool")


@app.exception_handler(Exception)
async def _log_unhandled_exception(request: Request, exc: Exception):
    log.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

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


def _require_teacher_page(request: Request) -> Optional[RedirectResponse]:
    """Returns a redirect-to-login Response if not authenticated, else None."""
    if auth.current_username(request):
        return None
    next_qs = f"?next={request.url.path}"
    return RedirectResponse(f"/teacher/login{next_qs}", status_code=303)


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


@app.get("/teacher/login", response_class=HTMLResponse)
async def teacher_login_page(request: Request, next: str = "/teacher", error: str | None = None):
    if auth.current_username(request):
        return RedirectResponse(next, status_code=303)
    return templates.TemplateResponse(
        request, "teacher_login.html",
        {"next": next, "error": error, "needs_setup": db.count_teachers() == 0},
    )


@app.post("/teacher/login")
async def teacher_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/teacher"),
):
    teacher = db.get_teacher_by_username(username)
    if not teacher or not auth.verify_password(password, teacher["password_hash"]):
        return RedirectResponse(
            f"/teacher/login?next={next}&error=Incorrect+username+or+password", status_code=303
        )
    token = auth.create_session(teacher["username"])
    response = RedirectResponse(next, status_code=303)
    response.set_cookie(auth.SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=auth.SESSION_TTL_SECONDS)
    return response


@app.post("/teacher/logout")
async def teacher_logout(request: Request):
    auth.destroy_session(request.cookies.get(auth.SESSION_COOKIE))
    response = RedirectResponse("/teacher/login", status_code=303)
    response.delete_cookie(auth.SESSION_COOKIE)
    return response


@app.get("/teacher/setup", response_class=HTMLResponse)
async def teacher_setup_page(request: Request, error: str | None = None):
    is_first_run = db.count_teachers() == 0
    if not is_first_run and not auth.current_username(request):
        return RedirectResponse("/teacher/login?next=/teacher/setup", status_code=303)
    return templates.TemplateResponse(
        request, "teacher_setup.html", {"is_first_run": is_first_run, "error": error}
    )


@app.post("/teacher/setup")
async def teacher_setup_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    is_first_run = db.count_teachers() == 0
    if not is_first_run and not auth.current_username(request):
        return RedirectResponse("/teacher/login?next=/teacher/setup", status_code=303)

    username = username.strip()
    if len(username) < 3:
        return RedirectResponse("/teacher/setup?error=Username+must+be+at+least+3+characters", status_code=303)
    if len(password) < 8:
        return RedirectResponse("/teacher/setup?error=Password+must+be+at+least+8+characters", status_code=303)
    if db.get_teacher_by_username(username):
        return RedirectResponse("/teacher/setup?error=That+username+is+already+taken", status_code=303)

    db.create_teacher(username, auth.hash_password(password))

    if is_first_run:
        token = auth.create_session(username)
        response = RedirectResponse("/teacher", status_code=303)
        response.set_cookie(auth.SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=auth.SESSION_TTL_SECONDS)
        return response
    return RedirectResponse("/teacher", status_code=303)


@app.get("/teacher", response_class=HTMLResponse)
async def teacher_dashboard(request: Request):
    if db.count_teachers() == 0:
        return RedirectResponse("/teacher/setup", status_code=303)
    redirect = _require_teacher_page(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request, "teacher.html",
        {"songs": _list_songs(), "current_teacher": auth.current_username(request),
         "license_info": licensing.get_current_license()},
    )


@app.get("/teacher/submissions", response_class=HTMLResponse)
async def teacher_submissions_page(request: Request, date: str | None = None):
    redirect = _require_teacher_page(request)
    if redirect:
        return redirect
    selected_date = date or date_cls.today().isoformat()
    return templates.TemplateResponse(
        request,
        "teacher_submissions.html",
        {"selected_date": selected_date, "current_teacher": auth.current_username(request)},
    )


@app.get("/teacher/editor", response_class=HTMLResponse)
async def teacher_editor_page(request: Request, song: str | None = None):
    redirect = _require_teacher_page(request)
    if redirect:
        return redirect
    existing_song = _load_song(song) if song else None
    return templates.TemplateResponse(
        request,
        "editor.html",
        {"songs": _list_songs(), "existing_song": existing_song, "current_teacher": auth.current_username(request)},
    )


@app.get("/teacher/monitor", response_class=HTMLResponse)
async def teacher_monitor_page(request: Request, song: str | None = None):
    redirect = _require_teacher_page(request)
    if redirect:
        return redirect
    songs = _list_songs()
    selected_song_id = song if (song and any(s["id"] == song for s in songs)) else (songs[0]["id"] if songs else None)
    return templates.TemplateResponse(
        request,
        "monitor.html",
        {"songs": songs, "selected_song_id": selected_song_id, "current_teacher": auth.current_username(request)},
    )


@app.get("/teacher/roster", response_class=HTMLResponse)
async def teacher_roster_page(request: Request):
    redirect = _require_teacher_page(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request, "roster.html", {"current_teacher": auth.current_username(request)},
    )


@app.get("/teacher/license", response_class=HTMLResponse)
async def teacher_license_page(request: Request, error: str | None = None, saved: bool = False):
    redirect = _require_teacher_page(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request, "teacher_license.html",
        {"current_teacher": auth.current_username(request),
         "license_info": licensing.get_current_license(), "error": error, "saved": saved},
    )


@app.post("/teacher/license")
async def teacher_license_submit(request: Request, license_key: str = Form(...)):
    redirect = _require_teacher_page(request)
    if redirect:
        return redirect
    if not licensing.save_license_key(license_key):
        return RedirectResponse("/teacher/license?error=That+license+key+is+invalid+or+expired.", status_code=303)
    return RedirectResponse("/teacher/license?saved=true", status_code=303)


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
async def api_create_song(payload: SongPayload, _teacher: str = Depends(auth.require_teacher_api)):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Title is required.")
    song_id = _unique_song_id(payload.title)
    song = _save_song(song_id, payload)
    return SongDetail(**song)


@app.put("/api/songs/{song_id}", response_model=SongDetail)
async def api_update_song(song_id: str, payload: SongPayload, _teacher: str = Depends(auth.require_teacher_api)):
    _load_song(song_id)  # 404s if it doesn't already exist
    song = _save_song(song_id, payload)
    return SongDetail(**song)


@app.post("/api/songs/import-musicxml", response_model=SongPayload)
async def api_import_musicxml(file: UploadFile = File(...), _teacher: str = Depends(auth.require_teacher_api)):
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
async def api_list_submissions(
    date: str | None = None, student: str | None = None, _teacher: str = Depends(auth.require_teacher_api)
):
    return [SubmissionRecord(**row) for row in db.list_submissions(date=date, student_name=student)]


@app.get("/api/roster", response_model=list[RosterEntry])
async def api_list_roster(_teacher: str = Depends(auth.require_teacher_api)):
    return [RosterEntry(**row) for row in db.list_roster()]


@app.post("/api/roster", response_model=RosterEntry, status_code=201)
async def api_add_student(payload: RosterAddRequest, _teacher: str = Depends(auth.require_teacher_api)):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")
    return RosterEntry(**db.add_student(payload.name, payload.consent_on_file))


@app.patch("/api/roster/{student_id}", response_model=dict)
async def api_update_student(
    student_id: int, payload: RosterUpdateRequest, _teacher: str = Depends(auth.require_teacher_api)
):
    if not db.set_student_active(student_id, payload.active):
        raise HTTPException(status_code=404, detail="No student with that id.")
    return {"ok": True}


@app.get("/api/roster/verify-code", response_model=CodeCheckResult)
async def api_verify_access_code(code: str):
    """Public (student-facing): confirms a code is valid without exposing
    the rest of the roster -- just the one matching student's first name,
    as a "Hi, Alex!" confirmation before they start practicing."""
    student = db.get_student_by_code(code)
    if not student:
        return CodeCheckResult(valid=False)
    return CodeCheckResult(valid=True, first_name=student["name"].split()[0])


@app.get("/api/my-submissions", response_model=list[MySubmissionRecord])
async def api_my_submissions(code: str):
    """Public (student-facing): a student's own past attempts, gated by
    their own access code -- never another student's."""
    return [MySubmissionRecord(**row) for row in db.list_submissions_for_code(code)]


@app.post("/api/submit", response_model=AssessmentReport)
async def submit_recording(
    song_id: str = Form(...),
    access_code: str = Form(...),
    file: UploadFile = File(...),
):
    student = db.get_student_by_code(access_code)
    if not student:
        raise HTTPException(status_code=400, detail="Unrecognized access code. Check with your teacher.")

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

    try:
        report = grade_submission(np.asarray(audio, dtype=np.float32), sr, target_notes)
    except Exception as exc:
        log.exception("Grading failed for song=%s student=%s", song_id, student["id"])
        raise HTTPException(
            status_code=400,
            detail="Could not grade this recording. Please record a longer take and try again.",
        ) from exc
    db.record_submission(
        student_id=student["id"],
        song_id=song_id,
        song_title=song["title"],
        report=report,
        take_filename=take_id,
    )
    await live_manager.mark_submitted_by_name(student["name"])
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
                requested_role = data.get("role")
                if requested_role == "student":
                    student = db.get_student_by_code(data.get("access_code") or "")
                    if not student:
                        await websocket.close(code=4400, reason="Unrecognized access code.")
                        return
                    role = "student"
                    await live_manager.student_join(websocket, student["name"])
                elif requested_role == "teacher":
                    if not auth.current_username_ws(websocket.cookies):
                        await websocket.close(code=4401, reason="Teacher login required.")
                        return
                    role = "teacher"
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
