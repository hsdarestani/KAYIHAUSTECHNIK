from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Final source-level cleanup for mixed German/English labels that may come from
# legacy templates restored before the product overlays.
for path in (ROOT / "templates").rglob("*.html"):
    text = path.read_text(encoding="utf-8")
    updated = (
        text.replace("Kein Wizard", "Kein Assistent")
        .replace("Wizard", "Assistent")
        .replace("Voice", "Spracheingabe")
        .replace("Work OS", "Handwerkssoftware")
    )
    if updated != text:
        path.write_text(updated, encoding="utf-8")

# Keep the old KAYI Next regression test aligned with the now fully German label.
test_path = ROOT / "tests" / "test_tooltime_rebuild.py"
if test_path.exists():
    test_text = test_path.read_text(encoding="utf-8")
    test_text = test_text.replace(
        'self.assertIn("Kein Wizard", form)',
        'self.assertIn("Kein Assistent", form)',
    )
    test_path.write_text(test_text, encoding="utf-8")

path = ROOT / "scripts" / "production_browser_smoke.py"
text = path.read_text(encoding="utf-8")
marker = "# KAYI German-only visible UI audit"
if marker not in text:
    if "import re\n" not in text:
        text = text.replace("import os\n", "import os\nimport re\n", 1)

    text = text.replace(
        '("/projects/new/", ("Projekt anlegen", "Kein Wizard", "Aufmaß / 3D")),',
        '("/projects/new/", ("Projekt anlegen", "Kein Assistent", "Aufmaß / 3D")),',
    )
    settings_anchor = '("/migration/tooltime/", ("Von ToolTime zu KAYI", "Import starten")),'
    if settings_anchor in text and '("/settings/", ("Einstellungen",)),' not in text:
        text = text.replace(
            settings_anchor,
            settings_anchor + '\n                ("/settings/", ("Einstellungen",)),',
            1,
        )

    anchor = '''    html = page.content()\n    for marker in markers:\n        if marker not in html:\n            fail(f"{path} is missing {marker!r}")\n'''
    addition = anchor + '''    # KAYI German-only visible UI audit. Check rendered text, not source code,\n    # so technical identifiers and API field names are ignored.\n    visible_text = page.locator("body").inner_text()\n    forbidden_visible = re.compile(r"\\b(?:Cancel|Save|Create|Edit|Delete|Upload|Provider|Wizard|Voice|Settings|Customer|Quote|Invoice|AI)\\b")\n    match = forbidden_visible.search(visible_text)\n    if match:\n        fail(f"{path} still exposes English UI text {match.group(0)!r}")\n    for forbidden_phrase in ("Work OS", "Create a room from photos", "Take or select room photos", "Detect and place space"):\n        if forbidden_phrase in visible_text:\n            fail(f"{path} still exposes English UI text {forbidden_phrase!r}")\n'''
    if anchor not in text:
        raise RuntimeError("Could not install German visible-text audit")
    text = text.replace(anchor, addition, 1)

    room_anchor = '''            visible_controls = page.locator('form input:not([type="hidden"]), form select, form textarea')\n            if visible_controls.count() < 4:\n                fail("new project flow has too few controls and appears broken")\n'''
    room_addition = room_anchor + '''\n            # Open a real project and exercise the Room Planner photo dialog.\n            page.goto(urljoin(base_url, "projects/"), wait_until="domcontentloaded", timeout=30_000)\n            project_hrefs = page.locator('a[href^="/projects/"]').evaluate_all("els => els.map(e => e.getAttribute('href')).filter(h => /^\\/projects\\/\\d+\\/$/.test(h))")\n            if not project_hrefs:\n                fail("German UI smoke could not find a project for Room Planner")\n            page.goto(urljoin(base_url, project_hrefs[0].lstrip("/")), wait_until="domcontentloaded", timeout=30_000)\n            planner_link = page.locator('a[href$="/room-planner/"]').first\n            if planner_link.count() != 1:\n                fail("project detail is missing Room Planner link")\n            planner_link.click()\n            page.wait_for_load_state("domcontentloaded")\n            trigger = page.locator('[data-rp-open-vision]').first\n            if trigger.count() != 1:\n                fail("Room Planner is missing photo recognition action")\n            trigger.click()\n            dialog = page.locator('[data-rp-vision-dialog][open]')\n            dialog.wait_for(state="attached", timeout=5_000)\n            dialog_text = dialog.inner_text()\n            for required in ("Raum aus Fotos aufbauen", "Foto aufnehmen", "Aus Galerie auswählen", "Raum erkennen & platzieren"):\n                if required not in dialog_text:\n                    fail(f"German Room Planner photo dialog is missing {required!r}")\n            room_forbidden = re.compile(r"\\b(?:Cancel|Save|Create|Edit|Delete|Upload|Provider|Wizard|Voice|AI)\\b")\n            match = room_forbidden.search(dialog_text)\n            if match:\n                fail(f"Room Planner still exposes English text {match.group(0)!r}")\n            for forbidden in ("Create a room from photos", "Take or select room photos", "Detect and place space"):\n                if forbidden in dialog_text:\n                    fail(f"Room Planner still exposes English text {forbidden!r}")\n            if page.locator('[data-rp-camera-files]').count() != 1:\n                fail("Room Planner is missing dedicated camera input")\n            if page.locator('[data-rp-gallery-files][multiple]').count() != 1:\n                fail("Room Planner is missing multi-select gallery input")\n            page.locator('[data-rp-close-vision]').first.click()\n'''
    if room_anchor not in text:
        raise RuntimeError("Could not install Room Planner German browser smoke")
    text = text.replace(room_anchor, room_addition, 1)

    field_anchor = '''            if page.locator(".nx-field-bottom a").count() != 3:\n                fail("technician mobile navigation must contain exactly Termine, Zeit and Konto")\n'''
    field_addition = field_anchor + '''            field_text = page.locator("body").inner_text()\n            field_forbidden = re.compile(r"\\b(?:Cancel|Save|Create|Edit|Delete|Upload|Provider|Wizard|Voice|Settings|Customer|Quote|Invoice|AI)\\b")\n            match = field_forbidden.search(field_text)\n            if match:\n                fail(f"technician field surface still exposes English UI text {match.group(0)!r}")\n'''
    if field_anchor in text:
        text = text.replace(field_anchor, field_addition, 1)

    path.write_text(text, encoding="utf-8")

print("KAYI German visible-text and Room Planner camera/gallery browser smoke installed.")
