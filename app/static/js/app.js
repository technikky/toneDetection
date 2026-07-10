/** Main wiring for the student session: exercise loading, mic capture
 * lifecycle, and submission to the Stage 9 grading endpoint.
 *
 * Stage 15: students authenticate with a teacher-issued access code
 * instead of typing their own name, so the roster stays teacher-managed.
 */
(function () {
  const root = document.getElementById("app-root");
  let currentSongId = root.dataset.selectedSong;
  let currentStream = null;
  let isRecording = false;
  let lastBlob = null;
  let codeIsValid = false;

  const recordBtn = document.getElementById("record-btn");
  const recordPulse = document.getElementById("record-pulse");
  const recordStatus = document.getElementById("record-status");
  const micError = document.getElementById("mic-error");
  const submitBtn = document.getElementById("submit-btn");
  const playback = document.getElementById("playback");
  const songSelect = document.getElementById("song-select");
  const tempoBadge = document.getElementById("tempo-badge");
  const codeInput = document.getElementById("access-code");
  const codeError = document.getElementById("student-name-error");
  const codeStatus = document.getElementById("access-code-status");
  const myAttemptsEl = document.getElementById("my-attempts");
  const playBtn = document.getElementById("play-btn");
  const pianoPlayer = createPianoPlayer(playBtn);
  let currentTuneObj = null;

  function currentCode() {
    return codeInput.value.trim().toUpperCase();
  }

  async function loadMyAttempts(code) {
    if (!code) {
      myAttemptsEl.innerHTML = '<p class="text-sm text-slate-500 dark:text-slate-400">Enter your access code above to see your history.</p>';
      return;
    }
    try {
      const res = await fetch(`/api/my-submissions?code=${encodeURIComponent(code)}`);
      const rows = res.ok ? await res.json() : [];
      if (!rows.length) {
        myAttemptsEl.innerHTML = '<p class="text-sm text-slate-500 dark:text-slate-400">No attempts yet.</p>';
        return;
      }
      myAttemptsEl.innerHTML = `<ul class="space-y-2 text-sm">${rows.slice(0, 8).map((r) => `
        <li class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2 last:border-0">
          <span class="text-slate-600 dark:text-slate-400">${r.song_title} <span class="text-slate-400 dark:text-slate-500">&middot; ${r.submitted_at.slice(0, 10)}</span></span>
          <span class="font-semibold">${r.overall_score}%</span>
        </li>`).join("")}</ul>`;
    } catch (err) {
      myAttemptsEl.innerHTML = '<p class="text-sm text-rose-600 dark:text-rose-400">Could not load your history.</p>';
    }
  }

  let verifyTimer = null;
  async function verifyCode() {
    const code = currentCode();
    codeIsValid = false;
    if (code.length < 4) {
      codeStatus.classList.add("hidden");
      myAttemptsEl.innerHTML = '<p class="text-sm text-slate-500 dark:text-slate-400">Enter your access code above to see your history.</p>';
      return;
    }
    try {
      const res = await fetch(`/api/roster/verify-code?code=${encodeURIComponent(code)}`);
      const result = await res.json();
      if (result.valid) {
        codeIsValid = true;
        codeStatus.textContent = `Hi, ${result.first_name}!`;
        codeStatus.className = "text-xs mt-1 text-emerald-600 dark:text-emerald-400";
        codeError.classList.add("hidden");
        sendJoin();
        loadMyAttempts(code);
      } else {
        codeStatus.textContent = "Code not recognized -- check with your teacher.";
        codeStatus.className = "text-xs mt-1 text-rose-600 dark:text-rose-400";
        loadMyAttempts(null);
      }
      codeStatus.classList.remove("hidden");
    } catch (err) {
      codeStatus.classList.add("hidden");
    }
  }

  codeInput.value = localStorage.getItem("accessCode") || "";
  codeInput.addEventListener("input", () => {
    codeInput.value = codeInput.value.toUpperCase();
    localStorage.setItem("accessCode", codeInput.value.trim());
    if (codeInput.value.trim()) codeError.classList.add("hidden");
    clearTimeout(verifyTimer);
    verifyTimer = setTimeout(verifyCode, 300);
  });

  playBtn.addEventListener("click", () => pianoPlayer.play(currentTuneObj));

  // Stage 14: live teacher/student session -- stream this student's pitch
  // to any connected teacher monitor, and auto-switch when the teacher
  // sends a new exercise to the class.
  function sendJoin() {
    if (!codeIsValid) return;
    live.send({ type: "join", role: "student", access_code: currentCode() });
  }

  const live = connectLiveSocket((message) => {
    if (message.type === "assignment" && message.song_id && message.song_id !== currentSongId) {
      window.location.href = `/student?song=${encodeURIComponent(message.song_id)}`;
    }
  });

  let lastPitchSendAt = 0;
  window.onLivePitchSample = (freq, level) => {
    if (!codeIsValid) return;
    const now = Date.now();
    if (now - lastPitchSendAt < 150) return;
    lastPitchSendAt = now;
    const hasFreq = freq && isFinite(freq) && freq > 0;
    live.send({
      type: "pitch",
      hz: hasFreq ? Math.round(freq * 10) / 10 : null,
      midi: hasFreq ? Math.round(hzToMidi(freq) * 100) / 100 : null,
      level: Math.round(level * 100) / 100,
    });
  };

  async function loadSong(songId) {
    const res = await fetch(`/api/songs/${songId}`);
    if (!res.ok) return;
    const song = await res.json();
    window.activeSongNotes = song.notes.map((n) => ({ midi: n.midi, solfege: n.solfege }));
    window.activeSong = song;
    const tunes = renderNotation(song.abc);
    currentTuneObj = tunes && tunes[0];
    tempoBadge.textContent = `${song.tempo_bpm} BPM · Key of ${song.key}`;
    document.getElementById("report-card").classList.add("hidden");
    submitBtn.disabled = true;
    playback.classList.add("hidden");
    pianoPlayer.stop();
  }

  songSelect.addEventListener("change", () => {
    window.location.href = `/student?song=${encodeURIComponent(songSelect.value)}`;
  });

  recordBtn.addEventListener("click", async () => {
    micError.classList.add("hidden");
    if (!isRecording) {
      if (!codeIsValid) {
        codeError.classList.remove("hidden");
        codeInput.focus();
        return;
      }
      try {
        currentStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (err) {
        micError.textContent = "Microphone access denied or unavailable: " + err.message;
        micError.classList.remove("hidden");
        return;
      }
      startRecording(currentStream);
      startPitchViz(currentStream);
      isRecording = true;
      recordPulse.classList.remove("hidden");
      recordStatus.textContent = "Recording… tap to stop";
      submitBtn.disabled = true;
      live.send({ type: "status", status: "recording" });
    } else {
      const { blob, url } = stopRecording();
      stopPitchViz();
      if (currentStream) currentStream.getTracks().forEach((t) => t.stop());
      isRecording = false;
      recordPulse.classList.add("hidden");
      recordStatus.textContent = "Tap to re-record";
      lastBlob = blob;
      playback.src = url;
      playback.classList.remove("hidden");
      submitBtn.disabled = false;
      live.send({ type: "status", status: "idle" });
    }
  });

  submitBtn.addEventListener("click", async () => {
    if (!lastBlob) return;
    submitBtn.disabled = true;
    submitBtn.textContent = "Grading…";
    try {
      const form = new FormData();
      form.append("song_id", currentSongId);
      form.append("access_code", currentCode());
      form.append("file", lastBlob, "take.wav");
      const res = await fetch("/api/submit", { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Grading failed");
      }
      const report = await res.json();
      renderReport(report);
      loadMyAttempts(currentCode());
    } catch (err) {
      micError.textContent = "Submission error: " + err.message;
      micError.classList.remove("hidden");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit for Grading";
    }
  });

  loadSong(currentSongId);
  if (codeInput.value.trim()) verifyCode();
})();
