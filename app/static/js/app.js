/** Main wiring for the student session: exercise loading, mic capture
 * lifecycle, and submission to the Stage 9 grading endpoint.
 */
(function () {
  const root = document.getElementById("app-root");
  let currentSongId = root.dataset.selectedSong;
  let currentStream = null;
  let isRecording = false;
  let lastBlob = null;

  const recordBtn = document.getElementById("record-btn");
  const recordPulse = document.getElementById("record-pulse");
  const recordStatus = document.getElementById("record-status");
  const micError = document.getElementById("mic-error");
  const submitBtn = document.getElementById("submit-btn");
  const playback = document.getElementById("playback");
  const songSelect = document.getElementById("song-select");
  const tempoBadge = document.getElementById("tempo-badge");

  async function loadSong(songId) {
    const res = await fetch(`/api/songs/${songId}`);
    if (!res.ok) return;
    const song = await res.json();
    window.activeSongNotes = song.notes.map((n) => ({ midi: n.midi, solfege: n.solfege }));
    window.activeSong = song;
    renderNotation(song.abc);
    tempoBadge.textContent = `${song.tempo_bpm} BPM · Key of ${song.key}`;
    document.getElementById("report-card").classList.add("hidden");
    submitBtn.disabled = true;
    playback.classList.add("hidden");
  }

  songSelect.addEventListener("change", () => {
    window.location.href = `/student?song=${encodeURIComponent(songSelect.value)}`;
  });

  recordBtn.addEventListener("click", async () => {
    micError.classList.add("hidden");
    if (!isRecording) {
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
    }
  });

  submitBtn.addEventListener("click", async () => {
    if (!lastBlob) return;
    submitBtn.disabled = true;
    submitBtn.textContent = "Grading…";
    try {
      const form = new FormData();
      form.append("song_id", currentSongId);
      form.append("file", lastBlob, "take.wav");
      const res = await fetch("/api/submit", { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Grading failed");
      }
      const report = await res.json();
      renderReport(report);
    } catch (err) {
      micError.textContent = "Submission error: " + err.message;
      micError.classList.remove("hidden");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit for Grading";
    }
  });

  loadSong(currentSongId);
})();
