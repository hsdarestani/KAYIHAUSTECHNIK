from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "scripts/production_browser_smoke.py"
MARKER = "            # A+BAU TOOLTIME PAY BROWSER SMOKE\n"
CLOSE = "            context.close()\n"

# The product UI is German-only. Keep technical provider identifiers in Python,
# settings JSON and environment variables, but do not expose English labels in
# the rendered Pay surfaces.
visible_replacements = {
    "templates/rebuild/tooltime_settings.html": {
        "Provider-Geheimnisse bleiben ausschließlich in der Server-Umgebung.": "Zugangsdaten des Zahlungsanbieters bleiben ausschließlich in der Server-Umgebung.",
        "Provider-Endpoint": "HTTPS-Adresse des Zahlungsanbieters",
        "Kulanz / Grace Days": "Kulanzfrist (Tage)",
        "Provider-Geheimnisse werden nur serverseitig über": "Zugangsdaten des Zahlungsanbieters werden nur serverseitig über",
        "Ohne echte Provider-Antwort wird keine Rechnung als bezahlt markiert.": "Ohne echte Antwort des Zahlungsanbieters wird keine Rechnung als bezahlt markiert.",
    },
    "templates/rebuild/payments.html": {
        "Provider-Transaktionen bleiben bis zum bestätigten Webhook ausstehend.": "Transaktionen des Zahlungsanbieters bleiben bis zur bestätigten Rückmeldung ausstehend.",
        "<span class=\"tt-eyebrow\">Checkout</span>": "<span class=\"tt-eyebrow\">Bezahlen</span>",
        "Provider-Referenz": "Anbieter-Referenz",
    },
    "templates/rebuild/payouts.html": {
        "Vom Provider bestätigte Einzel- oder Sammelauszahlungen.": "Vom Zahlungsanbieter bestätigte Einzel- oder Sammelauszahlungen.",
        "Provider-Referenz": "Anbieter-Referenz",
        "authentifizierten Provider-Ereignis": "authentifizierten Ereignis des Zahlungsanbieters",
    },
}

for rel, replacements in visible_replacements.items():
    template_path = ROOT / rel
    if not template_path.exists():
        raise RuntimeError(f"Pay UI language target missing: {rel}")
    template = template_path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        template = template.replace(old, new)
    template_path.write_text(template, encoding="utf-8")

settings_ui = (ROOT / "templates/rebuild/tooltime_settings.html").read_text(encoding="utf-8")
payments_ui = (ROOT / "templates/rebuild/payments.html").read_text(encoding="utf-8")
payouts_ui = (ROOT / "templates/rebuild/payouts.html").read_text(encoding="utf-8")
for forbidden in ("Provider-Endpoint", "Grace Days", "Provider-Geheimnisse"):
    if forbidden in settings_ui:
        raise RuntimeError(f"Pay settings still expose English UI text: {forbidden}")
for forbidden in ("Provider-Transaktionen", "Provider-Referenz", ">Checkout<"):
    if forbidden in payments_ui:
        raise RuntimeError(f"Pay payments page still exposes English UI text: {forbidden}")
for forbidden in ("Vom Provider ", "Provider-Referenz", "Provider-Ereignis"):
    if forbidden in payouts_ui:
        raise RuntimeError(f"Pay payouts page still exposes English UI text: {forbidden}")

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
    print("ToolTime Pay UI is German and browser smoke already runs in office context.")
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
    print("ToolTime Pay UI Germanized and browser smoke moved to authenticated office context; field permissions stay restricted.")
