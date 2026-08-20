from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "scripts/production_browser_smoke.py"
MARKER = "            # A+BAU PHASE 6 COMMUNICATION SETTINGS BROWSER SMOKE\n"
END_SENTINEL = '                fail("Live-Vorschau des Angebotsbetreffs ist leer")\n\n'
CLOSE = "            context.close()\n"

path = ROOT / REL
text = path.read_text(encoding="utf-8")

office_start = text.find("def run_office_surface(")
field_start = text.find("\ndef run_field_surface(", office_start)
if office_start < 0 or field_start < 0:
    raise RuntimeError("Phase 6 settings-smoke office/field anchors missing")

marker_pos = text.find(MARKER)
if marker_pos < 0:
    raise RuntimeError("Phase 6 communication-settings smoke marker missing")
if text.find(MARKER, marker_pos + 1) >= 0:
    raise RuntimeError("Phase 6 communication-settings smoke marker duplicated")

# Phase 6 was historically appended with rfind(context.close()), which can leave
# the commercial-settings assertions in the generic/field browser context after
# later parity layers split office and technician surfaces. Keep the exact block,
# but execute it only inside the authenticated office surface. Never weaken the
# product permission guard to satisfy a smoke test.
if not (office_start < marker_pos < field_start):
    sentinel_pos = text.find(END_SENTINEL, marker_pos)
    if sentinel_pos < 0:
        raise RuntimeError("Phase 6 communication-settings smoke end sentinel missing")
    block_end = sentinel_pos + len(END_SENTINEL)
    block = text[marker_pos:block_end]
    text = text[:marker_pos] + text[block_end:]

    office_start = text.find("def run_office_surface(")
    field_start = text.find("\ndef run_field_surface(", office_start)
    office_close = text.rfind(CLOSE, office_start, field_start)
    if office_close < 0:
        raise RuntimeError("Phase 6 settings-smoke office context close anchor missing")
    text = text[:office_close] + block + text[office_close:]

new_marker_pos = text.find(MARKER)
if not (office_start < new_marker_pos < field_start):
    raise RuntimeError("Phase 6 communication-settings smoke is not inside office context")

# The field surface must still test the protected endpoint as forbidden; the
# communication panel itself must never be expected there.
field_segment = text[field_start:]
if MARKER in field_segment:
    raise RuntimeError("Commercial communication settings are still tested as a field user")

path.write_text(text, encoding="utf-8")
compile(text, str(path), "exec")
print("Phase 6 Kommunikation-Smoke läuft ausschließlich im Office-Kontext; Mitarbeiterzugriff bleibt gesperrt.")
