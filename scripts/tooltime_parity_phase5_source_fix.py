from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "tooltime_parity_phase5_communication.py"
text = path.read_text(encoding="utf-8")

old_open = "    body = f'''<html><body style=\"font-family:Arial,sans-serif;font-size:11px;color:#202428\">"
new_open = "    body = f\"\"\"<html><body style=\"font-family:Arial,sans-serif;font-size:11px;color:#202428\">"
old_close = "</body></html>'''\n    return html_to_pdf_bytes"
new_close = "</body></html>\"\"\"\n    return html_to_pdf_bytes"

if old_open in text:
    text = text.replace(old_open, new_open, 1)
elif new_open not in text:
    raise RuntimeError("Phase 5 source-fix opening anchor missing")

if old_close in text:
    text = text.replace(old_close, new_close, 1)
elif new_close not in text:
    raise RuntimeError("Phase 5 source-fix closing anchor missing")

path.write_text(text, encoding="utf-8")
compile(text, str(path), "exec")
print("ToolTime Phase 5 source repair: quote PDF generator uses non-conflicting string delimiters.")
