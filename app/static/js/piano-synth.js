/** Stage 13: offline sampled-piano playback via ABCjs' synth engine, using a
 * locally vendored FluidR3_GM soundfont (app/static/vendor/soundfont) --
 * no internet required at runtime, unlike ABCjs' default remote soundfont URL.
 */
const PIANO_SOUNDFONT_URL = "/static/vendor/soundfont/FluidR3_GM/";

function createPianoPlayer(buttonEl) {
  let audioContext = null;
  let synth = null;
  let playing = false;

  function reset(label) {
    playing = false;
    buttonEl.disabled = false;
    buttonEl.textContent = label || "▶ Play";
  }

  async function stop() {
    if (synth) {
      try { synth.stop(); } catch (err) { /* already stopped */ }
    }
    if (audioContext) {
      try { await audioContext.close(); } catch (err) { /* already closed */ }
    }
    audioContext = null;
    synth = null;
    reset();
  }

  async function play(visualObj) {
    if (!visualObj) return;
    if (playing) { await stop(); return; }
    if (!window.ABCJS || !ABCJS.synth || !ABCJS.synth.CreateSynth) {
      reset("▶ Play (unsupported)");
      buttonEl.disabled = true;
      return;
    }

    buttonEl.disabled = true;
    buttonEl.textContent = "Loading…";
    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      synth = new ABCJS.synth.CreateSynth();
      await synth.init({
        audioContext,
        visualObj,
        options: {
          soundFontUrl: PIANO_SOUNDFONT_URL,
          program: 0, // General MIDI 0 = acoustic grand piano
          onEnded: () => reset(),
        },
      });
      await synth.prime();
      playing = true;
      buttonEl.disabled = false;
      buttonEl.textContent = "■ Stop";
      synth.start();
    } catch (err) {
      console.error("Piano playback failed:", err);
      reset("▶ Play (unavailable)");
      buttonEl.disabled = true;
    }
  }

  return { play, stop };
}
