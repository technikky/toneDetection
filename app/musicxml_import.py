"""Stage 13: import a MusicXML export (from MuseScore or any other notation
tool) into our exercise schema -- the target note/solfège matrix used for
grading, plus an equivalent ABC notation string for rendering (our vendored
ABCjs build renders ABC, not MusicXML).

Scope: single-part, single-voice, monophonic melodic lines (i.e. exactly
what a sight-singing exercise is). Only the first <part> is used; chords are
collapsed to their first note; only major keys get solfège assigned (movable
-do doesn't define minor-key syllables in this app). <score-timewise> is not
supported, only the far more common <score-partwise>.
"""
import io
import zipfile
from fractions import Fraction
from xml.etree import ElementTree as ET

from app.config import SOLFEGE_SEMITONE_OFFSETS

_STEP_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# Circle of fifths, major keys only: index 0 = 0 fifths (C), positive = sharps, negative = flats.
_FIFTHS_TO_MAJOR_KEY = {
    -7: "Cb", -6: "Gb", -5: "Db", -4: "Ab", -3: "Eb", -2: "Bb", -1: "F",
    0: "C",
    1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
}
# Letters sharped/flatted by a key, in application order.
_SHARP_ORDER = ["F", "C", "G", "D", "A", "E", "B"]
_FLAT_ORDER = ["B", "E", "A", "D", "G", "C", "F"]

_SOLFEGE_BY_OFFSET = {v: k for k, v in SOLFEGE_SEMITONE_OFFSETS.items()}


class MusicXmlImportError(ValueError):
    pass


def _extract_root_xml(raw: bytes) -> bytes:
    """Return the raw MusicXML bytes, unwrapping a compressed .mxl if needed."""
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            try:
                container = zf.read("META-INF/container.xml")
                root_path = ET.fromstring(container).find(".//rootfile").attrib["full-path"]
            except Exception as exc:
                raise MusicXmlImportError(
                    "Could not find the root MusicXML file inside this .mxl archive."
                ) from exc
            return zf.read(root_path)
    return raw


def _key_accidentals(fifths: int) -> dict:
    """Return {letter: alter} for the letters altered by this key signature."""
    accidentals = {}
    if fifths > 0:
        for letter in _SHARP_ORDER[:fifths]:
            accidentals[letter] = 1
    elif fifths < 0:
        for letter in _FLAT_ORDER[: -fifths]:
            accidentals[letter] = -1
    return accidentals


def _midi_from_pitch(step: str, alter: int, octave: int) -> int:
    return (octave + 1) * 12 + _STEP_SEMITONES[step] + alter


def _nearest_solfege(midi: int, tonic_pitch_class: int) -> str:
    interval = (midi - tonic_pitch_class) % 12
    best_name, best_dist = "Do", 99
    for offset, name in _SOLFEGE_BY_OFFSET.items():
        dist = min(abs(offset - interval), 12 - abs(offset - interval))
        if dist < best_dist:
            best_dist, best_name = dist, name
    return best_name


def _format_duration(quarters: Fraction) -> str:
    """Render a duration (in quarter notes, our ABC L:1/4 base unit) as an
    ABC length suffix, e.g. 1 -> "", 0.5 -> "/2", 1.5 -> "3/2", 2 -> "2"."""
    if quarters == 1:
        return ""
    if quarters.denominator == 1:
        return str(quarters.numerator)
    if quarters.numerator == 1:
        return f"/{quarters.denominator}"
    return f"{quarters.numerator}/{quarters.denominator}"


def _format_pitch(step: str, alter: int, octave: int, key_accidentals: dict) -> str:
    letter = step.upper()
    expected_alter = key_accidentals.get(letter, 0)
    mark = ""
    if alter != expected_alter:
        mark = {1: "^", -1: "_", 0: "="}.get(alter, "")

    if octave <= 4:
        return mark + letter + "," * (4 - octave)
    return mark + letter.lower() + "'" * (octave - 5)


def parse_musicxml(raw: bytes, fallback_title: str = "Imported Exercise") -> dict:
    """Parse a MusicXML (or .mxl) file into a dict shaped like SongPayload."""
    try:
        xml_bytes = _extract_root_xml(raw)
        root = ET.fromstring(xml_bytes)
    except MusicXmlImportError:
        raise
    except ET.ParseError as exc:
        raise MusicXmlImportError(f"Could not parse this file as XML: {exc}") from exc

    if root.tag != "score-partwise":
        raise MusicXmlImportError(
            "Only <score-partwise> MusicXML is supported (MuseScore's default export)."
        )

    part = root.find("part")
    if part is None:
        raise MusicXmlImportError("No <part> found in this MusicXML file.")

    title_el = root.find(".//work/work-title")
    if title_el is None or not (title_el.text or "").strip():
        title_el = root.find(".//movement-title")
    title = (title_el.text.strip() if title_el is not None and title_el.text else fallback_title)

    divisions = 1
    fifths = 0
    beats, beat_type = 4, 4
    tempo_bpm = 90
    key_accidentals: dict = {}
    tonic_letter = "C"
    tonic_pitch_class = 0

    abc_body = []
    notes_out = []
    cursor_quarters = Fraction(0)
    step_index = 0
    measures_since_barline = 0

    for measure in part.findall("measure"):
        attributes = measure.find("attributes")
        if attributes is not None:
            div_el = attributes.find("divisions")
            if div_el is not None and div_el.text:
                divisions = int(div_el.text)
            fifths_el = attributes.find("key/fifths")
            if fifths_el is not None and fifths_el.text:
                fifths = int(fifths_el.text)
                tonic_letter = _FIFTHS_TO_MAJOR_KEY.get(fifths, "C")
                key_accidentals = _key_accidentals(fifths)
                tonic_alter = key_accidentals.get(tonic_letter[0], 0)
                tonic_pitch_class = _midi_from_pitch(tonic_letter[0], tonic_alter, 4) % 12
            beats_el = attributes.find("time/beats")
            beat_type_el = attributes.find("time/beat-type")
            if beats_el is not None and beat_type_el is not None:
                beats, beat_type = int(beats_el.text), int(beat_type_el.text)

        sound_el = measure.find(".//sound[@tempo]")
        if sound_el is not None and "tempo" in sound_el.attrib:
            tempo_bpm = round(float(sound_el.attrib["tempo"]))

        for note_el in measure.findall("note"):
            dur_el = note_el.find("duration")
            duration_quarters = (
                Fraction(int(dur_el.text), divisions) if dur_el is not None and dur_el.text else Fraction(0)
            )

            if note_el.find("chord") is not None:
                # Collapse chords onto the melody note already emitted.
                continue

            if note_el.find("rest") is not None:
                abc_body.append("z" + _format_duration(duration_quarters))
                cursor_quarters += duration_quarters
                continue

            pitch_el = note_el.find("pitch")
            if pitch_el is None:
                cursor_quarters += duration_quarters
                continue

            step = pitch_el.find("step").text
            alter = int(pitch_el.find("alter").text) if pitch_el.find("alter") is not None else 0
            octave = int(pitch_el.find("octave").text)

            midi = _midi_from_pitch(step, alter, octave)
            solfege = _nearest_solfege(midi, tonic_pitch_class)

            step_index += 1
            start_seconds = float(cursor_quarters) * 60.0 / tempo_bpm
            duration_seconds = float(duration_quarters) * 60.0 / tempo_bpm
            notes_out.append({
                "step": step_index,
                "midi": midi,
                "solfege": solfege,
                "start": round(start_seconds, 3),
                "duration": round(duration_seconds, 3),
            })

            abc_body.append(_format_pitch(step, alter, octave, key_accidentals) + _format_duration(duration_quarters))
            cursor_quarters += duration_quarters

        abc_body.append("|")
        measures_since_barline += 1
        if measures_since_barline % 4 == 0:
            abc_body.append("\n")

    if not notes_out:
        raise MusicXmlImportError("No playable notes found in this MusicXML file.")

    if abc_body and abc_body[-1] in ("|", "\n"):
        while abc_body and abc_body[-1] in ("|", "\n"):
            abc_body.pop()
    abc_body.append("|]")

    abc = (
        f"X:1\nT:{title}\nM:{beats}/{beat_type}\nL:1/4\nQ:1/4={tempo_bpm}\n"
        f"K:{tonic_letter}\n{' '.join(abc_body)}"
    )

    return {
        "title": title,
        "difficulty": "Beginner",
        "key": tonic_letter,
        "tempo_bpm": tempo_bpm,
        "abc": abc,
        "notes": notes_out,
    }
