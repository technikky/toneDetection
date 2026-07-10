/** Stage 4: offline audio capture pipeline. Captures raw PCM via the Web
 * Audio API (not MediaRecorder, which would produce a webm/opus container)
 * and compiles it into a structurally valid local .wav Blob on stop.
 */
let rec = {
  audioCtx: null,
  scriptNode: null,
  chunks: [],
  sampleRate: null,
};

function startRecording(stream) {
  rec.chunks = [];
  rec.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  rec.sampleRate = rec.audioCtx.sampleRate;
  const source = rec.audioCtx.createMediaStreamSource(stream);

  rec.scriptNode = rec.audioCtx.createScriptProcessor(2048, 1, 1);
  const silentGain = rec.audioCtx.createGain();
  silentGain.gain.value = 0;
  source.connect(rec.scriptNode);
  rec.scriptNode.connect(silentGain);
  silentGain.connect(rec.audioCtx.destination);

  rec.scriptNode.onaudioprocess = (e) => {
    rec.chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
  };
}

function stopRecording() {
  if (rec.scriptNode) { rec.scriptNode.disconnect(); rec.scriptNode.onaudioprocess = null; }
  const merged = mergeFloat32Chunks(rec.chunks);
  const sampleRate = rec.sampleRate;
  if (rec.audioCtx) rec.audioCtx.close();
  const blob = encodeWavBlob(merged, sampleRate);
  rec = { audioCtx: null, scriptNode: null, chunks: [], sampleRate: null };
  return { blob, url: URL.createObjectURL(blob) };
}
