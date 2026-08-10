from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates/erp/settings.html"
text = path.read_text(encoding="utf-8")
marker = "data-settings-help"

if marker not in text:
    pattern = re.compile(r'<button\s+type=["\']button["\']\s*>', flags=re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if not matches:
        raise RuntimeError("No bare settings buttons found; settings guidance contract changed")
    text, count = pattern.subn('<button type="button" data-settings-help>', text)
    if count < 1:
        raise RuntimeError("Settings button guidance was not applied")
    path.write_text(text, encoding="utf-8")
    print(f"KAYI settings guidance attached to {count} previously unbound buttons.")
else:
    print("KAYI settings guidance already installed.")
