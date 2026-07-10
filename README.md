# Sight-Singing Studio

An offline, commercial-grade sight-singing and solfège assessment tool. It runs entirely on a
teacher's local machine (`http://127.0.0.1:8000`) with no internet connection required at
runtime -- all fonts, JS libraries, and ML models are bundled locally.

Students read sheet music rendered from ABC notation, record themselves singing, and get an
instant report scoring both **pitch accuracy** (against 12-tone equal temperament) and
**pronunciation accuracy** (whether they sang the correct solfège syllable -- Do, Re, Mi, Fa,
Sol, La, Ti). Teachers get a dashboard to assign exercises, create/edit sheet music, and review
scores by student and by day.

## Features

- **Sight-singing exercises** -- ABC-notation sheet music rendered client-side via ABCjs, with a
  real-time pitch/chromagram feedback canvas (Meyda + Pitchfinder) while the student sings.
- **Dual-engine grading** -- `librosa.pyin` for studio-grade pitch tracking, plus an offline
  MFCC + scikit-learn classifier for solfège syllable recognition.
- **Sheet-music editor** (`/teacher/editor`) -- teachers can write/edit ABC notation with a live
  preview and build the target note/solfège matrix used for grading, or load an existing
  exercise to modify it.
- **Submission history** (`/teacher/submissions`) -- every graded take is attributed to a
  student and persisted to a local SQLite database, browsable by date and student.
- **Dark/light mode**, responsive layout, offline-first throughout.
- **Standalone executable** -- packaged via PyInstaller into a single zero-config `.exe`.

## Quick start (development)

**One click:** double-click `start-dev.bat`. If `offline-sdk/portable-python/`
is present it uses that directly -- a self-contained Python with every
dependency pre-installed, so this works with **no internet and no system
Python at all**. Otherwise it falls back to a system Python, installing
dependencies from `offline-sdk/` if present or PyPI if not. Either way it
starts the dev server and opens your browser to `http://127.0.0.1:8000`
automatically. Close the window or press Ctrl+C to stop.

Manual equivalent:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The role picker links to `/teacher` and `/student`.

The solfège classifier ships pre-trained (`app/models/solfege_classifier.joblib`). To
regenerate the training data or retrain it:

```bash
python scripts/generate_solfege_training_data.py
python scripts/train_solfege_classifier.py
```

## Building the standalone executable

```bash
pip install pyinstaller
pyinstaller sight_singing.spec
```

Produces `dist/SightSingingStudio.exe` -- a single file with templates, static assets, the
exercise catalog, and the trained classifier bundled in. Recorded takes and the submissions
database are written next to the `.exe` at runtime (not inside the temp extraction dir), so
they persist across runs.

## Project structure

```
app/
  main.py              FastAPI routes: pages, exercise API, submission/grading, song CRUD
  config.py             Central paths (frozen-exe aware)
  db.py                 SQLite persistence: students + graded submissions
  schemas.py             Pydantic request/response models
  dsp/                   Pitch extraction (librosa.pyin), solfège classifier, grading engine
  data/
    songs/               Exercise catalog (ABC notation + target note/solfège matrix, as JSON)
    training/            Synthetic solfège training audio (regenerable, not committed)
    uploads/              Recorded student takes (runtime data, not committed)
  models/                 Trained solfège classifier
  static/
    js/                    Front-end logic (recording, live pitch viz, notation, editor, results)
    vendor/                 Offline copies of ABCjs, Meyda, Pitchfinder, compiled Tailwind CSS
  templates/               Jinja2 pages (role picker, teacher dashboard/editor/submissions, student)
scripts/                  One-off training-data generation and classifier training scripts
run_app.py / sight_singing.spec   PyInstaller entry point and build spec
```

## Tech stack

- **Backend**: FastAPI, librosa/NumPy (pitch), scikit-learn (solfège classification), SQLite
- **Frontend**: Tailwind CSS (compiled locally, no CDN), ABCjs (notation), Meyda + Pitchfinder
  (live pitch feedback), vanilla JS
- **Packaging**: PyInstaller (one-file Windows executable)

## Security & deployment notes

The app is designed to run exclusively on `http://127.0.0.1` -- this is what allows browsers to
grant microphone access without HTTPS while keeping everything air-gapped. It is not intended to
be exposed on a network.
