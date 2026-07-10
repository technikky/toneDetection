/** Stage 14: teacher live-session monitor -- send an exercise to the class
 * and watch each connected student's live pitch/level in real time.
 */
(function () {
  const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const STATUS_LABEL = { idle: "Idle", recording: "Recording", submitted: "Submitted" };
  const STATUS_CLASS = {
    idle: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400",
    recording: "bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300",
    submitted: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  };

  const root = document.getElementById("monitor-root");
  const songSelect = document.getElementById("song-select");
  const editLink = document.getElementById("edit-link");
  const sendBtn = document.getElementById("send-btn");
  const sendStatus = document.getElementById("send-status");
  const rosterEl = document.getElementById("roster");
  const rosterCount = document.getElementById("roster-count");

  const rowsByName = new Map();

  function midiToNoteName(midi) {
    if (!Number.isFinite(midi)) return "—";
    const rounded = Math.round(midi);
    const name = NOTE_NAMES[((rounded % 12) + 12) % 12];
    const octave = Math.floor(rounded / 12) - 1;
    return `${name}${octave}`;
  }

  function updateEditLink() {
    editLink.href = songSelect.value ? `/teacher/editor?song=${encodeURIComponent(songSelect.value)}` : "/teacher/editor";
  }
  songSelect.addEventListener("change", updateEditLink);
  updateEditLink();

  function makeRow(name) {
    const row = document.createElement("div");
    row.className = "flex items-center gap-4 rounded-xl border border-slate-100 dark:border-slate-800 p-3";
    row.innerHTML = `
      <div class="flex-1 min-w-0">
        <p class="font-medium truncate">${name}</p>
        <p class="text-xs text-slate-500 dark:text-slate-400 reading">&mdash;</p>
      </div>
      <span class="pill status"></span>
      <div class="w-24 h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
        <div class="level-bar h-full bg-brand-500 transition-all" style="width:0%"></div>
      </div>
    `;
    rosterEl.appendChild(row);
    return row;
  }

  function renderRoster(students) {
    rosterCount.textContent = `${students.length} connected`;
    if (!students.length) {
      rosterEl.innerHTML = '<p class="text-sm text-slate-500 dark:text-slate-400">No students connected yet. Have them open the Student page.</p>';
      rowsByName.clear();
      return;
    }
    if (rosterEl.querySelector("p")) rosterEl.innerHTML = "";

    const seen = new Set();
    students.forEach((s) => {
      seen.add(s.name);
      let row = rowsByName.get(s.name);
      if (!row) {
        row = makeRow(s.name);
        rowsByName.set(s.name, row);
      }
      const statusEl = row.querySelector(".status");
      statusEl.textContent = STATUS_LABEL[s.status] || s.status;
      statusEl.className = `pill status ${STATUS_CLASS[s.status] || STATUS_CLASS.idle}`;
      applyReading(row, s.hz, s.midi, s.level);
    });

    [...rowsByName.keys()].forEach((name) => {
      if (!seen.has(name)) {
        rowsByName.get(name).remove();
        rowsByName.delete(name);
      }
    });
  }

  function applyReading(row, hz, midi, level) {
    const readingEl = row.querySelector(".reading");
    readingEl.textContent = hz ? `${midiToNoteName(midi)} · ${hz.toFixed(1)} Hz` : "—";
    const barEl = row.querySelector(".level-bar");
    barEl.style.width = `${Math.min(100, Math.max(0, (level || 0) * 300))}%`;
  }

  const live = connectLiveSocket((message) => {
    if (message.type === "roster") {
      renderRoster(message.students);
    } else if (message.type === "pitch_update") {
      const row = rowsByName.get(message.student_name);
      if (row) applyReading(row, message.hz, message.midi, message.level);
    }
  });

  live.send({ type: "join", role: "teacher" });

  sendBtn.addEventListener("click", () => {
    const songId = songSelect.value;
    if (!songId) return;
    const difficulty = songSelect.options[songSelect.selectedIndex].text;
    live.send({ type: "assign", song_id: songId, difficulty });
    sendStatus.className = "text-sm mt-3 text-emerald-600 dark:text-emerald-400";
    sendStatus.textContent = "Sent! Connected students will switch to this exercise automatically.";
    sendStatus.classList.remove("hidden");
  });
})();
