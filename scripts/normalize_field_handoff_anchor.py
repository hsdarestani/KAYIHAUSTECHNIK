from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates" / "rebuild" / "appointment_detail.html"
text = path.read_text(encoding="utf-8")
pattern = re.compile(r'<textarea\b[^>]*\bname="report_text"[^>]*>', re.I)
replacement = '<textarea class="nx-control" name="report_text" data-voice-target placeholder="Was wurde vor Ort gemacht? Zum Beispiel: Rohrbruch lokalisiert, Leitung repariert, Anlage geprüft …">'
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise RuntimeError("Could not normalize field report textarea contract")
path.write_text(text, encoding="utf-8")
print("KAYI field report textarea normalized for final voice/KI handoff layer.")
