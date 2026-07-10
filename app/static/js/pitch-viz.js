/** Stage 6: real-time pitch (Pitchfinder) + chromagram/waveform (Meyda)
 * feedback sandbox. Purely visual — the authoritative grade always comes
 * from the backend librosa pipeline in Stage 7-9.
 */
const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

let pv = {
  audioCtx: null,
  scriptNode: null,
  meydaAnalyzer: null,
  detectPitch: null,
  waveCanvas: null,
  chromaCanvas: null,
};

function hzToMidi(freq) {
  return 69 + 12 * Math.log2(freq / 440);
}

function midiToNoteName(midi) {
  const rounded = Math.round(midi);
  const name = NOTE_NAMES[((rounded % 12) + 12) % 12];
  const octave = Math.floor(rounded / 12) - 1;
  return `${name}${octave}`;
}

function nearestTargetSolfege(midi) {
  const notes = window.activeSongNotes || [];
  if (!notes.length) return "—";
  let best = notes[0];
  let bestDist = Infinity;
  for (const n of notes) {
    const d = Math.abs(n.midi - midi);
    if (d < bestDist) { bestDist = d; best = n; }
  }
  return best.solfege;
}

function drawWaveform(buffer) {
  const canvas = pv.waveCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, w, h);
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#818cf8";
  ctx.beginPath();
  const step = Math.max(1, Math.floor(buffer.length / w));
  for (let x = 0; x < w; x++) {
    const sample = buffer[x * step] || 0;
    const y = h / 2 + sample * (h / 2) * 0.9;
    x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.stroke();
}

function drawChroma(chroma) {
  const canvas = pv.chromaCanvas;
  if (!canvas || !chroma) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, w, h);
  const barW = w / chroma.length;
  const maxVal = Math.max(...chroma, 0.001);
  chroma.forEach((val, i) => {
    const barH = (val / maxVal) * (h - 16);
    ctx.fillStyle = "#6366f1";
    ctx.fillRect(i * barW + 2, h - barH, barW - 4, barH);
    ctx.fillStyle = "#94a3b8";
    ctx.font = "9px sans-serif";
    ctx.fillText(NOTE_NAMES[i], i * barW + 4, h - 2);
  });
}

function updateLivePitch(freq) {
  const hzEl = document.getElementById("live-hz");
  const noteEl = document.getElementById("live-note");
  const targetEl = document.getElementById("live-target");
  if (!freq || !isFinite(freq) || freq <= 0) {
    hzEl.textContent = "—";
    noteEl.textContent = "—";
    targetEl.textContent = "—";
    return;
  }
  const midi = hzToMidi(freq);
  hzEl.textContent = freq.toFixed(1);
  noteEl.textContent = midiToNoteName(midi);
  targetEl.textContent = nearestTargetSolfege(midi);
}

function startPitchViz(stream) {
  pv.waveCanvas = document.getElementById("waveform-canvas");
  pv.chromaCanvas = document.getElementById("chroma-canvas");
  pv.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const source = pv.audioCtx.createMediaStreamSource(stream);

  pv.detectPitch = Pitchfinder.YIN({ sampleRate: pv.audioCtx.sampleRate });

  pv.scriptNode = pv.audioCtx.createScriptProcessor(2048, 1, 1);
  const silentGain = pv.audioCtx.createGain();
  silentGain.gain.value = 0;
  source.connect(pv.scriptNode);
  pv.scriptNode.connect(silentGain);
  silentGain.connect(pv.audioCtx.destination);

  pv.scriptNode.onaudioprocess = (e) => {
    const input = e.inputBuffer.getChannelData(0);
    drawWaveform(input);
    const freq = pv.detectPitch(input);
    updateLivePitch(freq);
  };

  pv.meydaAnalyzer = Meyda.createMeydaAnalyzer({
    audioContext: pv.audioCtx,
    source,
    bufferSize: 512,
    featureExtractors: ["chroma"],
    callback: (features) => drawChroma(features.chroma),
  });
  pv.meydaAnalyzer.start();
}

function stopPitchViz() {
  if (pv.meydaAnalyzer) pv.meydaAnalyzer.stop();
  if (pv.scriptNode) { pv.scriptNode.disconnect(); pv.scriptNode.onaudioprocess = null; }
  if (pv.audioCtx) pv.audioCtx.close();
  pv = { ...pv, audioCtx: null, scriptNode: null, meydaAnalyzer: null };
  updateLivePitch(null);
}
