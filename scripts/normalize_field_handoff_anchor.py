from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates" / "rebuild" / "appointment_detail.html"
text = path.read_text(encoding="utf-8")
pattern = re.compile(r'<textarea\b[^>]*\bname="report_text"[^>]*>', re.I)
replacement = '<textarea class="nx-control" name="report_text" data-voice-target placeholder="Was wurde vor Ort gemacht? Zum Beispiel: Rohrbruch lokalisiert, Leitung repariert, Anlage geprüft …">'
match = pattern.search(text)
if not match:
    raise RuntimeError("Could not normalize field report textarea contract")
text = text[:match.start()] + replacement + text[match.end():]

if "data-field-voice" not in text:
    match = pattern.search(text)
    if not match:
        raise RuntimeError("Could not locate normalized report textarea for recording panel")
    recording = '''<div class="nx-voice-capture" data-field-voice data-transcribe-url="{% url 'next-appointment-voice' event.pk %}">
          <label class="nx-voice-consent"><input type="checkbox" data-field-voice-consent><span>Der Ansprechpartner stimmt der Vor-Ort-Sprachaufnahme und der KI-Auswertung zu.</span></label>
          <div class="nx-voice-controls"><button class="nx-btn nx-btn-primary" type="button" data-field-record>🎙 Vor-Ort-Sprachnotiz aufnehmen</button><button class="nx-btn" type="button" data-field-transcribe hidden>✦ Aufnahme mit KI auswerten</button><span class="nx-record-status" data-field-record-status>Noch keine Aufnahme.</span></div>
          <audio class="nx-voice-preview" data-field-voice-preview controls hidden></audio>
          <input type="file" name="voice_note" accept="audio/*" data-field-voice-file hidden><input type="hidden" name="voice_transcript">
        </div>
        '''
    text = text[:match.start()] + recording + text[match.start():]

path.write_text(text, encoding="utf-8")
print("KAYI field report textarea and recording panel normalized for final voice/KI handoff layer.")
