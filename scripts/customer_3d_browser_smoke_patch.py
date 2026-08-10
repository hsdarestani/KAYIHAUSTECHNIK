from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "production_browser_smoke.py"
text = path.read_text(encoding="utf-8")

# The previous KAYI Next smoke expected the old long-form helper copy. The new
# progressive customer form deliberately replaces that sentence, so update only
# the obsolete visible marker while retaining the route/page assertion itself.
text = text.replace('"Nur das eintragen"', '"Weitere Angaben"')
text = text.replace("'Nur das eintragen'", "'Weitere Angaben'")

marker = "KAYI customer form and 3D KI polish smoke"
if marker not in text:
    project_anchor = '''            if visible_controls.count() < 4:\n                fail("new project flow has too few controls and appears broken")\n'''
    customer_block = '''            if visible_controls.count() < 4:\n                fail("new project flow has too few controls and appears broken")\n\n            # KAYI customer form and 3D KI polish smoke\n            page.goto(urljoin(base_url, "customers/new/"), wait_until="domcontentloaded", timeout=30_000)\n            if page.locator('[data-location-details]').count() != 1:\n                fail("customer form is missing progressive execution-location disclosure")\n            if page.locator('[data-location-details]').evaluate("el => el.open"):\n                fail("optional execution location is expanded by default")\n            customer_text = page.locator('body').inner_text()\n            if 'Floor' in customer_text or 'Access notes' in customer_text:\n                fail("customer form still exposes English location labels")\n            if 'Abweichenden Einsatzort hinzufügen' not in customer_text:\n                fail("customer form has no clear optional execution-location action")\n            # Continue the existing project-form smoke on the page it expects.\n            page.goto(urljoin(base_url, "projects/new/"), wait_until="domcontentloaded", timeout=30_000)\n'''
    if project_anchor not in text:
        raise RuntimeError("KAYI Next browser smoke project anchor changed")
    text = text.replace(project_anchor, customer_block, 1)

    planner_anchor = '''                if page.locator('[data-rp-add-object]').count() < 20:\n                    fail("Room Planner Pro object library is incomplete")\n'''
    planner_block = '''                if page.locator('[data-rp-add-object]').count() < 20:\n                    fail("Room Planner Pro object library is incomplete")\n                if page.locator('[data-rp-ki-card]:visible').count() != 1:\n                    fail("3D planner KI assistant is not clearly visible")\n                if page.locator('[data-rp-ai-command]').count() != 1 or page.locator('[data-rp-run-ai]').count() != 1:\n                    fail("3D planner KI command controls are incomplete")\n                first_example = page.locator('[data-rp-ai-example]').first\n                if first_example.count() != 1:\n                    fail("3D planner KI examples are missing")\n                first_example.click()\n                if not page.locator('[data-rp-ai-command]').input_value().strip():\n                    fail("3D planner KI example does not populate the command field")\n                planner_text = page.locator('body').inner_text()\n                for forbidden in ('Characteristics', 'Room overview', 'Doors & Windows', 'Save version', 'Live distances', 'AI sets'):\n                    if forbidden in planner_text:\n                        fail(f"3D planner still exposes English text: {forbidden}")\n                panel_font = float(page.locator('.rp-panel-title b').first.evaluate("el => parseFloat(getComputedStyle(el).fontSize)"))\n                object_font = float(page.locator('[data-rp-add-object] b').first.evaluate("el => parseFloat(getComputedStyle(el).fontSize)"))\n                if panel_font < 14 or object_font < 11:\n                    fail(f"3D planner typography is still too small: panel={panel_font}px object={object_font}px")\n                csrf_cookies = [cookie for cookie in page.context.cookies() if cookie.get('name') == 'csrftoken']\n                if not csrf_cookies:\n                    fail("3D planner did not receive a CSRF cookie for safe save requests")\n'''
    if planner_anchor not in text:
        raise RuntimeError("Room Planner Pro browser smoke anchor changed")
    text = text.replace(planner_anchor, planner_block, 1)
path.write_text(text, encoding="utf-8")
print("KAYI customer form and 3D KI browser smoke installed.")
