/** Stage 10: renders the Stage 9 grading report — score tiles, per-note
 * grid, and a time-aligned pitch error graph.
 */
function renderReport(report) {
  document.getElementById("report-card").classList.remove("hidden");
  document.getElementById("pitch-score").textContent = `${report.pitch_accuracy}%`;
  document.getElementById("pronun-score").textContent = `${report.pronunciation_accuracy}%`;

  const grid = document.getElementById("note-grid");
  grid.innerHTML = "";
  report.notes.forEach((n) => {
    const cell = document.createElement("div");
    const bothCorrect = n.pitch_correct && n.solfege_correct;
    const noneCorrect = !n.pitch_correct && !n.solfege_correct;
    const colorClass = bothCorrect
      ? "bg-emerald-500 text-white"
      : noneCorrect
        ? "bg-rose-500 text-white"
        : "bg-amber-400 text-slate-900";
    cell.className = `note-cell rounded-lg p-2 text-center text-xs font-semibold ${colorClass}`;
    cell.innerHTML = `<div>${n.target_solfege}</div><div class="text-[10px] font-normal opacity-80">${n.detected_solfege || "—"}</div>`;
    cell.title = `Step ${n.step}: target ${n.target_solfege} (MIDI ${n.target_midi}) — detected ${n.detected_note_name || "n/a"} / ${n.detected_solfege || "n/a"}`;
    grid.appendChild(cell);
  });

  drawErrorGraph(report);
}

function drawErrorGraph(report) {
  const canvas = document.getElementById("error-graph");
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, w, h);

  const notes = report.notes;
  const contour = report.pitch_contour;
  if (!notes.length) return;

  const scoreEnd = Math.max(...notes.map((n) => n.start + n.duration));
  const allMidi = notes.map((n) => n.target_midi).concat(
    contour.map((p) => p[1]).filter((v) => isFinite(v))
  );
  const minMidi = Math.min(...allMidi) - 2;
  const maxMidi = Math.max(...allMidi) + 2;

  const xOf = (t) => (t / scoreEnd) * (w - 20) + 10;
  const yOf = (m) => h - 15 - ((m - minMidi) / (maxMidi - minMidi)) * (h - 30);

  // Target step line.
  ctx.strokeStyle = "#475569";
  ctx.lineWidth = 2;
  ctx.beginPath();
  notes.forEach((n, i) => {
    const x1 = xOf(n.start), x2 = xOf(n.start + n.duration), y = yOf(n.target_midi);
    ctx.moveTo(x1, y);
    ctx.lineTo(x2, y);
  });
  ctx.stroke();

  // Detected contour (rescaled onto the same score-relative time axis).
  const recDuration = Math.max(...notes.map((n) => n.start + n.duration), 0.001);
  const contourEnd = contour.length ? Math.max(...contour.map((p) => p[0])) : recDuration;
  const timeScale = contourEnd > 0 ? scoreEnd / contourEnd : 1;

  ctx.strokeStyle = "#818cf8";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  contour.forEach(([t, midi], i) => {
    const x = xOf(t * timeScale), y = yOf(midi);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Per-note correctness markers.
  notes.forEach((n) => {
    const x = xOf(n.start + n.duration / 2);
    const y = yOf(n.target_midi);
    ctx.fillStyle = n.pitch_correct ? "#34d399" : "#fb7185";
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  });
}
