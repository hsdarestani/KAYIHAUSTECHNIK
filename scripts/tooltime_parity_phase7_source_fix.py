from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "tooltime_parity_phase7_e2e_flow.py"
text = path.read_text(encoding="utf-8")

old_open = "    body = f'''<html><body style=\"font-family:Arial,sans-serif;font-size:11px;color:#202428\">\n"
new_open = '    body = f"""<html><body style="font-family:Arial,sans-serif;font-size:11px;color:#202428">\n'
old_close = "</body></html>'''\n    payload = html_to_pdf_bytes(inject_business_pdf_identity(body, org=quote.organization, document_kind=\"Auftragsbestätigung\"))\n"
new_close = ' </body></html>"""\n    payload = html_to_pdf_bytes(inject_business_pdf_identity(body, org=quote.organization, document_kind="Auftragsbestätigung"))\n'

if old_open in text:
    text = text.replace(old_open, new_open, 1)
if old_close in text:
    text = text.replace(old_close, new_close, 1)

# Keep the patcher itself compile-safe before the assembly runner executes it.
compile(text, str(path), "exec")
path.write_text(text, encoding="utf-8")
print("ToolTime Phase 7 source repair: Auftragsbestätigung-PDF uses non-conflicting string delimiters.")
