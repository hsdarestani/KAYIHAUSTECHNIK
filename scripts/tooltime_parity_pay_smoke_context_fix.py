from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "scripts/production_browser_smoke.py"
MARKER = "            # A+BAU TOOLTIME PAY BROWSER SMOKE\n"
CLOSE = "            context.close()\n"

path = ROOT / REL
text = path.read_text(encoding="utf-8")

office_start = text.find("def run_office_surface(")
field_start = text.find("\ndef run_field_surface(", office_start)
if office_start < 0 or field_start < 0:
    raise RuntimeError("Pay browser-smoke office/field surface anchors missing")

marker_pos = text.find(MARKER)
if marker_pos < 0:
    raise RuntimeError("Pay browser-smoke marker missing")

# The Pay patch historically used rfind(context.close()), which placed the
# finance checks in the technician/field surface. Move that exact generated
# block into the authenticated office surface instead of weakening permissions.
if office_start < marker_pos < field_start:
    compile(text, str(path), "exec")
    print("ToolTime Pay browser smoke already runs in office context.")
else:
    block_end = text.find(CLOSE, marker_pos)
    if block_end < 0:
        raise RuntimeError("Pay browser-smoke block end anchor missing")
    block = text[marker_pos:block_end]
    text = text[:marker_pos] + text[block_end:]

    office_start = text.find("def run_office_surface(")
    field_start = text.find("\ndef run_field_surface(", office_start)
    office_close = text.rfind(CLOSE, office_start, field_start)
    if office_close < 0:
        raise RuntimeError("Pay browser-smoke office context close anchor missing")
    text = text[:office_close] + block + text[office_close:]

    new_marker_pos = text.find(MARKER)
    if not (office_start < new_marker_pos < field_start):
        raise RuntimeError("Pay browser-smoke was not moved into office context")
    path.write_text(text, encoding="utf-8")
    compile(text, str(path), "exec")
    print("ToolTime Pay browser smoke moved to authenticated office context; field permissions stay restricted.")
