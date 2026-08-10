from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates" / "rebuild" / "appointment_detail.html"
text = path.read_text(encoding="utf-8")

report_pattern = re.compile(r'<textarea\b[^>]*\bname="report_text"[^>]*>', re.I)
replacement = '<textarea class="nx-control" name="report_text" data-voice-target placeholder="Was wurde vor Ort gemacht? Zum Beispiel: Rohrbruch lokalisiert, Leitung repariert, Anlage geprüft …">'
match = report_pattern.search(text)
if not match:
    raise RuntimeError("Could not normalize field report textarea contract")
text = text[:match.start()] + replacement + text[match.end():]

if "data-field-voice" not in text:
    match = report_pattern.search(text)
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

if "data-customer-reviewed" not in text:
    signature_heading = re.search(r'<b>\s*Kundenunterschrift\s*</b>', text, re.I)
    if not signature_heading:
        raise RuntimeError("Could not locate customer signature section")
    section_start = text.rfind('<div class="nx-doc-section">', 0, signature_heading.start())
    if section_start < 0:
        raise RuntimeError("Could not locate customer signature section wrapper")
    review = '''<div class="nx-doc-section"><div class="nx-handoff-review"><label><input type="checkbox" name="customer_reviewed" value="1" data-customer-reviewed required><span><b>Gemeinsam geprüft</b><br>Arbeitsbericht, ausgeführte Leistungen und Material wurden mit dem Ansprechpartner vor Ort durchgegangen.</span></label></div></div>
      '''
    text = text[:section_start] + review + text[section_start:]

text = text.replace("✓ Einsatz dokumentieren", "✓ Einsatz abschließen & PDF erstellen")

if "data-handoff-result" not in text:
    form_start = text.find('data-documentation-form')
    if form_start < 0:
        raise RuntimeError("Could not locate documentation form")
    form_end = text.find('</form>', form_start)
    if form_end < 0:
        raise RuntimeError("Could not locate documentation form end")
    result = '''<div class="nx-handoff-result" data-handoff-result hidden><b>✓ Einsatz abgeschlossen</b><p>Der unterschriebene Arbeitsnachweis wurde im Projekt gespeichert und steht als PDF zur Übergabe bereit.</p><div class="nx-actions"><a class="nx-btn nx-btn-primary" data-handoff-pdf target="_blank" download>PDF öffnen / herunterladen</a><button class="nx-btn" type="button" data-handoff-share>PDF teilen</button></div></div>
      '''
    text = text[:form_end] + result + text[form_end:]

path.write_text(text, encoding="utf-8")
print("KAYI field recording, customer review and PDF handoff anchors normalized for final KI layer.")
