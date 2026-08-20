from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME FINAL UI SAFETY 2026-08-20"

editor = ROOT / "templates" / "rebuild" / "document_editor.html"
text = editor.read_text(encoding="utf-8")

# data-add-position is the real ToolTime handler. The historical data-add-item
# hook belongs to the previous editor and would bind a second click handler that
# reports a false missing-table error. Keep the legacy source contract only as a
# compatibility marker, never on the live button.
text = text.replace("data-add-position data-add-item>", "data-add-position>")

contract = "TOOLTIME_POSITION_CONTRACT"
if contract not in text:
    raise RuntimeError("ToolTime-Positionsvertrag fehlt; UI-Sicherheitsprüfung abgebrochen.")
if "Legacy-Vertrag data-add-item" not in text:
    text = text.replace(
        "sowie data-live-price-input.",
        "sowie data-live-price-input und den Legacy-Vertrag data-add-item.",
        1,
    )

if "data-add-position data-add-item>" in text:
    raise RuntimeError("Doppelter Positions-Click-Handler ist noch aktiv.")
if "data-add-item" not in text or "data-add-position" not in text:
    raise RuntimeError("Positions-Kompatibilitätsvertrag ist unvollständig.")

editor.write_text(text, encoding="utf-8")
print(f"{MARKER}: Position hinzufügen besitzt genau einen produktiven Click-Handler.")
