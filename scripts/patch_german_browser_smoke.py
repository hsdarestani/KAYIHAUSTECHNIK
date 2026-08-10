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

path = ROOT / "scripts" / "production_browser_smoke.py"
text = path.read_text(encoding="utf-8")
marker = "# KAYI German-only visible UI audit"
if marker not in text:
    text = text.replace('(\"/projects/new/\", (\"Projekt anlegen\", \"Kein Wizard\", \"Aufmaß / 3D\")),', '(\"/projects/new/\", (\"Projekt anlegen\", \"Kein Assistent\", \"Aufmaß / 3D\")),')

    anchor = '''    html = page.content()\n    for marker in markers:\n        if marker not in html:\n            fail(f"{path} is missing {marker!r}")\n'''
    addition = anchor + '''    # KAYI German-only visible UI audit. This intentionally checks rendered\n    # text instead of source code so data attributes and technical identifiers\n    # are not mistaken for user-visible language.\n    visible_text = page.locator("body").inner_text()\n    for forbidden in ("Work OS", "Kein Wizard", " Voice ", " Cancel ", " Save ", " Create ", " Edit ", " Delete ", " Upload ", " Provider "):\n        if forbidden.strip() in visible_text.splitlines():\n            fail(f"{path} still exposes English UI text {forbidden.strip()!r}")\n'''
    if anchor not in text:
        raise RuntimeError("Could not install German visible-text audit")
    text = text.replace(anchor, addition, 1)

    room_anchor = '''            visible_controls = page.locator('form input:not([type="hidden"]), form select, form textarea')\n            if visible_controls.count() < 4:\n                fail("new project flow has too few controls and appears broken")\n'''
    room_addition = room_anchor + '''\n            # Open a real project and exercise the Room Planner photo dialog.\n            page.goto(urljoin(base_url, "projects/"), wait_until="domcontentloaded", timeout=30_000)\n            project_hrefs = page.locator('a[href^="/projects/"]').evaluate_all("els => els.map(e => e.getAttribute('href')).filter(h => /^\\/projects\\/\\d+\\/$/.test(h))")\n            if not project_hrefs:\n                fail("German UI smoke could not find a project for Room Planner")\n            page.goto(urljoin(base_url, project_hrefs[0].lstrip("/")), wait_until="domcontentloaded", timeout=30_000)\n            planner_link = page.locator('a[href$="/room-planner/"]').first\n            if planner_link.count() != 1:\n                fail("project detail is missing Room Planner link")\n            planner_link.click()\n            page.wait_for_load_state("domcontentloaded")\n            trigger = page.locator('[data-rp-open-vision]').first\n            if trigger.count() != 1:\n                fail("Room Planner is missing photo recognition action")\n            trigger.click()\n            dialog = page.locator('[data-rp-vision-dialog][open]')\n            dialog.wait_for(state="attached", timeout=5_000)\n            dialog_text = dialog.inner_text()\n            for required in ("Raum aus Fotos aufbauen", "Foto aufnehmen", "Aus Galerie auswählen", "Raum erkennen & platzieren"):\n                if required not in dialog_text:\n                    fail(f"German Room Planner photo dialog is missing {required!r}")\n            for forbidden in ("Create a room from photos", "Take or select room photos", "Cancel", "Detect and place space", "AI setzt"):\n                if forbidden in dialog_text:\n                    fail(f"Room Planner still exposes English text {forbidden!r}")\n            if page.locator('[data-rp-camera-files]').count() != 1:\n                fail("Room Planner is missing dedicated camera input")\n            if page.locator('[data-rp-gallery-files][multiple]').count() != 1:\n                fail("Room Planner is missing multi-select gallery input")\n            page.locator('[data-rp-close-vision]').first.click()\n'''
    if room_anchor not in text:
        raise RuntimeError("Could not install Room Planner German browser smoke")
    text = text.replace(room_anchor, room_addition, 1)
    path.write_text(text, encoding="utf-8")

print("KAYI German visible-text and Room Planner camera/gallery browser smoke installed.")
