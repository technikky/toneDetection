/** Stage 12: teacher sheet-music editor -- create/edit an exercise's ABC
 * notation and the target note/solfège matrix used for grading.
 */
(function () {
  const SOLFEGE_SYLLABLES = ["Do", "Re", "Mi", "Fa", "Sol", "La", "Ti"];
  const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

  const root = document.getElementById("editor-root");
  const existingSong = JSON.parse(root.dataset.existingSong || "null");

  const heading = document.getElementById("editor-heading");
  const loadSelect = document.getElementById("load-existing");
  const titleInput = document.getElementById("f-title");
  const difficultySelect = document.getElementById("f-difficulty");
  const keyInput = document.getElementById("f-key");
  const tempoInput = document.getElementById("f-tempo");
  const abcTextarea = document.getElementById("f-abc");
  const abcError = document.getElementById("abc-error");
  const notesBody = document.getElementById("notes-body");
  const addNoteBtn = document.getElementById("add-note");
  const saveBtn = document.getElementById("save-btn");
  const saveStatus = document.getElementById("save-status");
  const playBtn = document.getElementById("play-btn");
  const pianoPlayer = createPianoPlayer(playBtn);
  let currentTuneObj = null;

  playBtn.addEventListener("click", () => pianoPlayer.play(currentTuneObj));

  function midiToNoteName(midi) {
    if (!Number.isFinite(midi)) return "";
    const name = NOTE_NAMES[((midi % 12) + 12) % 12];
    const octave = Math.floor(midi / 12) - 1;
    return `${name}${octave}`;
  }

  function makeNoteRow(note) {
    const tr = document.createElement("tr");
    tr.className = "note-row border-b border-slate-100 dark:border-slate-800 last:border-0";
    tr.innerHTML = `
      <td class="py-1 pr-2 step-cell text-slate-500 dark:text-slate-400"></td>
      <td class="py-1 pr-2"><input type="number" class="input midi-input" min="0" max="127" value="${note.midi}" style="width:4.5rem" /></td>
      <td class="py-1 pr-2 note-name-cell text-slate-500 dark:text-slate-400 whitespace-nowrap"></td>
      <td class="py-1 pr-2">
        <select class="input solfege-input" style="width:5rem">
          ${SOLFEGE_SYLLABLES.map((s) => `<option value="${s}" ${s === note.solfege ? "selected" : ""}>${s}</option>`).join("")}
        </select>
      </td>
      <td class="py-1 pr-2"><input type="number" class="input start-input" step="0.001" min="0" value="${note.start}" style="width:4.5rem" /></td>
      <td class="py-1 pr-2"><input type="number" class="input duration-input" step="0.001" min="0.01" value="${note.duration}" style="width:4.5rem" /></td>
      <td class="py-1"><button type="button" class="remove-note text-rose-500 hover:text-rose-700 px-1" aria-label="Remove note">&times;</button></td>
    `;
    const midiInput = tr.querySelector(".midi-input");
    const nameCell = tr.querySelector(".note-name-cell");
    const updateName = () => { nameCell.textContent = midiToNoteName(parseInt(midiInput.value, 10)); };
    midiInput.addEventListener("input", updateName);
    updateName();
    tr.querySelector(".remove-note").addEventListener("click", () => {
      tr.remove();
      renumberRows();
    });
    return tr;
  }

  function renumberRows() {
    [...notesBody.querySelectorAll(".note-row")].forEach((tr, i) => {
      tr.querySelector(".step-cell").textContent = i + 1;
    });
  }

  function addNote(note) {
    notesBody.appendChild(makeNoteRow(note));
    renumberRows();
  }

  addNoteBtn.addEventListener("click", () => {
    const rows = notesBody.querySelectorAll(".note-row");
    const last = rows.length ? rows[rows.length - 1] : null;
    const lastStart = last ? parseFloat(last.querySelector(".start-input").value) || 0 : 0;
    const lastDur = last ? parseFloat(last.querySelector(".duration-input").value) || 0.5 : 0;
    addNote({ midi: 60, solfege: "Do", start: lastStart + lastDur, duration: 0.5 });
  });

  let previewTimer = null;
  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(() => {
      abcError.classList.add("hidden");
      try {
        const tunes = renderNotation(abcTextarea.value, "notation-preview");
        currentTuneObj = tunes && tunes[0];
        if (!document.querySelector("#notation-preview svg")) {
          abcError.textContent = "This ABC notation didn't produce any sheet music -- check the syntax.";
          abcError.classList.remove("hidden");
          currentTuneObj = null;
        }
      } catch (err) {
        abcError.textContent = "Could not render this ABC notation: " + err.message;
        abcError.classList.remove("hidden");
        currentTuneObj = null;
      }
      pianoPlayer.stop();
    }, 300);
  }
  abcTextarea.addEventListener("input", schedulePreview);

  function populateFields(song) {
    titleInput.value = song ? song.title : "";
    difficultySelect.value = song ? song.difficulty : "Beginner";
    keyInput.value = song ? song.key : "C";
    tempoInput.value = song ? song.tempo_bpm : 90;
    abcTextarea.value = song ? song.abc : "X:1\nT:New Exercise\nM:4/4\nL:1/4\nQ:1/4=90\nK:C\nC D E F |]";
    notesBody.innerHTML = "";
    const notes = song ? song.notes : [{ midi: 60, solfege: "Do", start: 0, duration: 0.667 }];
    notes.forEach(addNote);
    schedulePreview();
  }

  function loadForm(song) {
    heading.textContent = song ? `Edit: ${song.title}` : "New Exercise";
    populateFields(song);
  }

  const importBtn = document.getElementById("import-musicxml-btn");
  const importInput = document.getElementById("import-musicxml-input");
  const importStatus = document.getElementById("import-status");

  importBtn.addEventListener("click", () => importInput.click());

  importInput.addEventListener("change", async () => {
    const file = importInput.files[0];
    if (!file) return;
    importStatus.className = "text-sm mb-6 text-slate-500 dark:text-slate-400";
    importStatus.textContent = `Importing ${file.name}…`;
    importStatus.classList.remove("hidden");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/songs/import-musicxml", { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
      }
      const parsed = await res.json();
      populateFields(parsed);
      heading.textContent = existingSong ? `Edit: ${existingSong.title}` : "New Exercise";
      importStatus.className = "text-sm mb-6 text-emerald-600 dark:text-emerald-400";
      importStatus.textContent = `Imported "${parsed.title}" -- review the notes/ABC below, then Save.`;
    } catch (err) {
      importStatus.className = "text-sm mb-6 text-rose-600 dark:text-rose-400";
      importStatus.textContent = "Could not import: " + err.message;
    } finally {
      importInput.value = "";
    }
  });

  loadSelect.addEventListener("change", () => {
    window.location.href = loadSelect.value
      ? `/teacher/editor?song=${encodeURIComponent(loadSelect.value)}`
      : "/teacher/editor";
  });

  function collectPayload() {
    const notes = [...notesBody.querySelectorAll(".note-row")].map((tr, i) => ({
      step: i + 1,
      midi: parseInt(tr.querySelector(".midi-input").value, 10),
      solfege: tr.querySelector(".solfege-input").value,
      start: parseFloat(tr.querySelector(".start-input").value),
      duration: parseFloat(tr.querySelector(".duration-input").value),
    }));
    return {
      title: titleInput.value.trim(),
      difficulty: difficultySelect.value,
      key: keyInput.value.trim() || "C",
      tempo_bpm: parseInt(tempoInput.value, 10) || 90,
      abc: abcTextarea.value,
      notes,
    };
  }

  function showStatus(message, isError) {
    saveStatus.textContent = message;
    saveStatus.className = `text-sm mt-3 ${isError ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`;
  }

  saveBtn.addEventListener("click", async () => {
    const payload = collectPayload();
    if (!payload.title) { showStatus("Title is required.", true); titleInput.focus(); return; }
    if (!payload.notes.length) { showStatus("Add at least one note.", true); return; }
    if (payload.notes.some((n) => Number.isNaN(n.midi) || Number.isNaN(n.start) || Number.isNaN(n.duration))) {
      showStatus("Every note needs a valid MIDI, start, and duration.", true);
      return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = "Saving…";
    try {
      const url = existingSong ? `/api/songs/${existingSong.id}` : "/api/songs";
      const method = existingSong ? "PUT" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
      }
      const saved = await res.json();
      showStatus(`Saved "${saved.title}".`, false);
      if (!existingSong) {
        window.location.href = `/teacher/editor?song=${encodeURIComponent(saved.id)}`;
      }
    } catch (err) {
      showStatus("Could not save: " + err.message, true);
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = "Save Exercise";
    }
  });

  loadForm(existingSong);
})();
