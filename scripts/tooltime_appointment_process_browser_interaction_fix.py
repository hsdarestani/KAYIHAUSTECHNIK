from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME APPOINTMENT BROWSER INTERACTION FIX 2026-08-21"


def run(module) -> None:
    rel = "scripts/production_browser_smoke.py"
    text = module.read(rel)

    old_labels = 'for label in ("Terminname", "Mitarbeiter hinzufügen", "Leistungsgruppe hinzufügen", "Position hinzufügen", "Arbeitsbericht"):'
    new_labels = 'for label in ("Terminname", "Mitarbeiter hinzufügen", "Leistungsgruppe hinzufügen", "Arbeitsbericht"):'
    if old_labels in text:
        text = text.replace(old_labels, new_labels, 1)

    old_editor = '''                if office_page.locator('[data-service-editor]').count() != 1:
                    fail("appointment service editor is missing")
'''
    new_editor = '''                if office_page.locator('[data-service-editor]').count() != 1:
                    fail("appointment service editor is missing")
                office_page.click('[data-add-service-group]')
                if office_page.locator('[data-add-service-row]').count() < 1:
                    fail("appointment service group did not expose Position hinzufügen")
                if office_page.locator('[data-service-row]').count() < 1:
                    fail("appointment service group did not create an initial position row")
'''
    if "appointment service group did not expose Position hinzufügen" not in text:
        if old_editor not in text:
            raise RuntimeError("Appointment browser interaction fix: service editor anchor fehlt")
        text = text.replace(old_editor, new_editor, 1)

    for marker in (
        new_labels,
        "office_page.click('[data-add-service-group]')",
        "appointment service group did not expose Position hinzufügen",
        "appointment service group did not create an initial position row",
    ):
        if marker not in text:
            raise RuntimeError(f"Appointment browser interaction fix guard missing: {marker}")

    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")
    print(f"{MARKER}: empty appointment service editor is exercised through real group/position interaction.")
