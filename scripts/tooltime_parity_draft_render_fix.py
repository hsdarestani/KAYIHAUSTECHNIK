from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME DRAFT RENDER FIX 2026-08-20"

path = ROOT / "templates" / "rebuild" / "document_editor.html"
text = path.read_text(encoding="utf-8")
old = '<textarea class="nx-control" name="closing_text" rows="9">{{ commercial.closing_text|default:document.outro_text|default:\'\' }}</textarea>'
new = '<textarea class="nx-control" name="closing_text" rows="9">{% if commercial and commercial.closing_text %}{{ commercial.closing_text }}{% elif document %}{{ document.outro_text|default:\'\' }}{% endif %}</textarea>'

if new not in text:
    if old not in text:
        raise RuntimeError("Schlusstext-Anker für sicheren Entwurf wurde nicht gefunden.")
    text = text.replace(old, new, 1)

# Neue Angebote und Rechnungen besitzen vor dem ersten Speichern bewusst noch kein
# Dokumentobjekt. Im finalen Template darf deshalb kein Filterargument ungeprüft
# ein Attribut von document auflösen.
if "default:document.outro_text" in text:
    raise RuntimeError("Unsicherer document.outro_text-Zugriff ist noch vorhanden.")
if "{% elif document %}{{ document.outro_text" not in text:
    raise RuntimeError("Sicherer Schlusstext-Fallback fehlt.")

path.write_text(text, encoding="utf-8")
print(f"{MARKER}: Neue Angebots- und Rechnungsentwürfe rendern ohne vorhandenes Dokumentobjekt.")
