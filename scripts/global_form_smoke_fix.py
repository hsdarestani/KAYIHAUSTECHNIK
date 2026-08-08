from pathlib import Path

path = Path("scripts/production_browser_smoke.py")
text = path.read_text(encoding="utf-8")
old = '''            wizard_form = page.locator("form").first
            if wizard_form.count() and not (wizard_form.get_attribute("data-kayi-form-audit") or "").startswith("skip:specialized"):
                fail("project wizard was not protected from generic form restructuring")
'''
new = '''            wizard_form = page.locator("form:has(section.wizard-step)").first
            if wizard_form.count() != 1:
                fail("project wizard steps are not contained in a single form")
            if not (wizard_form.get_attribute("data-kayi-form-audit") or "").startswith("skip:specialized"):
                fail("project wizard was not protected from generic form restructuring")
'''
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise RuntimeError("Project wizard smoke selector block was not found")
path.write_text(text, encoding="utf-8")

final = path.read_text(encoding="utf-8")
if 'form:has(section.wizard-step)' not in final:
    raise RuntimeError("Project wizard smoke selector fix did not apply")

print("KAYI global form smoke selector fix applied and verified.")
